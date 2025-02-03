from . import gitlab

GET, POST, PUT = gitlab.GET, gitlab.POST, gitlab.PUT


class Approvals(gitlab.Resource):
    """Approval info for a MergeRequest."""

    def refetch_info(self):
        approver_url = f'/projects/{self.project_id}/merge_requests/{self.iid}/approvals'

        self._info = self._api.call(GET(approver_url))

    @property
    def iid(self):
        return self.info['iid']

    @property
    def project_id(self):
        return self.info['project_id']

    @property
    def approvals_required(self):
        return self.info['approvals_required']

    @property
    def approvals_left(self):
        return self.info.get("approvals_left", 0) or 0

    @property
    def sufficient(self):
        return not self.approvals_left

    @property
    def approver_usernames(self):
        return [who['user']['username'] for who in self.info['approved_by']]

    @property
    def approver_ids(self):
        """Return the uids of the approvers."""
        return [who['user']['id'] for who in self.info['approved_by']]

    def reapprove(self):
        """Impersonates the approvers and re-approves the merge_request as them.

        The idea is that we want to get the approvers, push the rebased branch
        (which may invalidate approvals, depending on GitLab settings) and then
        restore the approval status.
        """
        self.approve(self)

    def approve(self, obj):
        """Approve an object which can be a merge_request or an approval."""
        approve_url = f'/projects/{obj.project_id}/merge_requests/{obj.iid}/approve'

        for uid in self.approver_ids:
            self._api.call(POST(approve_url), sudo=uid)
