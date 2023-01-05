from . import gitlab


GET, POST = gitlab.GET, gitlab.POST


class Pipeline(gitlab.Resource):
    def __init__(self, api, info, project_id):
        info['project_id'] = project_id
        super().__init__(api, info)

    @classmethod
    def pipelines_by_branch(
            cls, project_id, branch, api, *,
            ref=None,
            status=None,
            order_by='id',
            sort='desc',
    ):
        params = {
            'ref': branch if ref is None else ref,
            'order_by': order_by,
            'sort': sort,
        }
        if status is not None:
            params['status'] = status
        pipelines_info = api.call(GET(
            f'/projects/{project_id}/pipelines',
            params,
        ))

        return [cls(api, pipeline_info, project_id) for pipeline_info in pipelines_info]

    @classmethod
    def pipelines_by_merge_request(cls, project_id, merge_request_iid, api):
        """Fetch all pipelines for a merge request in descending order of pipeline ID."""
        pipelines_info = api.call(GET(
            f'/projects/{project_id}/merge_requests/{merge_request_iid}/pipelines'
        ))
        pipelines_info.sort(key=lambda pipeline_info: pipeline_info['id'], reverse=True)
        return [cls(api, pipeline_info, project_id) for pipeline_info in pipelines_info]

    @property
    def project_id(self):
        return self.info['project_id']

    @property
    def id(self):
        return self.info['id']

    @property
    def status(self):
        return self.info['status']

    @property
    def ref(self):
        return self.info['ref']

    @property
    def sha(self):
        return self.info['sha']

    def cancel(self):
        return self._api.call(POST(
            f'/projects/{self.project_id}/pipelines/{self.id}/cancel',
        ))
