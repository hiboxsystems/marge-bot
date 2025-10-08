import logging as log
import time
from collections import namedtuple
from tempfile import TemporaryDirectory

from . import git
from . import job
from . import merge_request as merge_request_module
from . import single_merge_job
from . import store
from .project import Project

MergeRequest = merge_request_module.MergeRequest


class Bot:
    def __init__(self, *, api, config):
        self._api = api
        self._config = config

        self._matching_projects_last_refresh = None
        self._cached_projects = None

        user = config.user
        opts = config.merge_opts

        if not user.is_admin:
            assert not opts.reapprove, (
                f"{user.username} is not an admin, can't impersonate!"
            )
            assert not opts.add_reviewers, (
                f"{user.username} is not an admin, can't lookup Reviewed-by: email addresses"
            )

    def start(self):
        skip_clone = self._config.merge_opts.fusion is Fusion.gitlab_rebase
        with TemporaryDirectory() as root_dir:
            if self._config.use_only_gitlab_api:
                repo_manager = store.ApiOnlyRepoManager(
                    user=self.user,
                    root_dir=root_dir,
                    skip_clone=skip_clone,
                    timeout=self._config.git_timeout,
                    reference=self._config.git_reference_repo,
                )
            elif self._config.use_https:
                repo_manager = store.HttpsRepoManager(
                    user=self.user,
                    root_dir=root_dir,
                    skip_clone=skip_clone,
                    auth_token=self._config.auth_token,
                    timeout=self._config.git_timeout,
                    reference=self._config.git_reference_repo,
                )
            else:
                repo_manager = store.SshRepoManager(
                    user=self.user,
                    root_dir=root_dir,
                    skip_clone=skip_clone,
                    ssh_key_file=self._config.ssh_key_file,
                    timeout=self._config.git_timeout,
                    reference=self._config.git_reference_repo,
                )
            self._run(repo_manager)

    @property
    def user(self):
        return self._config.user

    @property
    def api(self):
        return self._api

    def _run(self, repo_manager):
        time_to_sleep_between_merges_in_secs = 1
        time_to_sleep_when_no_mrs_found_in_secs = 15
        while True:
            project, merge_request = self._get_assigned_merge_requests()

            if merge_request:
                self._process_merge_request(repo_manager, project, merge_request)
                if not self._config.cli:
                    # Continue with the next MR without sleeping
                    time.sleep(time_to_sleep_between_merges_in_secs)
                    continue

            if self._config.cli:
                return

            log.debug('Sleeping for %s seconds...', time_to_sleep_when_no_mrs_found_in_secs)
            time.sleep(time_to_sleep_when_no_mrs_found_in_secs)

    def _get_assigned_merge_requests(self):
        log.debug('Fetching merge requests assigned to me...')
        my_merge_requests = MergeRequest.fetch_all_open_assigned_to_me(
            user=self.user,
            api=self._api,
            merge_order=self._config.merge_order,
        )

        self._refresh_cached_projects(forced=False)

        for merge_request in my_merge_requests:
            if merge_request.project_id not in self._cached_projects:
                # We might have just gotten access to this project, so force a check.
                self._refresh_cached_projects(forced=True)

            if merge_request.project_id not in self._cached_projects:
                log.debug('Ignoring MR %d from project ID %d because no project info found',
                          merge_request.iid, merge_request.project_id)
                continue

            if not self._cached_projects[merge_request.project_id]:
                log.debug('Ignoring MR %d from project ID %d because the project is not handled by me',
                          merge_request.iid, merge_request.project_id)
                continue

            return (self._cached_projects[merge_request.project_id], merge_request)

        return (None, None)

    def _refresh_cached_projects(self, forced):
        if forced or not self._cached_projects or self._matching_projects_last_refresh < (time.time() - 900):
            my_projects = Project.fetch_all_mine(self._api)
            project_regexp = self._config.project_regexp

            self._cached_projects = {}
            for project in my_projects:
                if project_regexp.match(project.path_with_namespace):
                    self._cached_projects[project.id] = project
                else:
                    self._cached_projects[project.id] = False

            self._matching_projects_last_refresh = time.time()

    def _process_merge_request(self, repo_manager, project, merge_request):
        if not merge_request:
            log.debug('Nothing to merge at this point...')
            return

        try:
            repo = repo_manager.repo_for_project(project)
        except git.GitError:
            log.exception("Couldn't initialize repository for project!")
            raise

        log.debug('Attempting to merge MR...')
        merge_job = self._get_single_job(
            project=project,
            merge_request=merge_request,
            repo=repo,
            config=self._config,
            options=self._config.merge_opts,
        )
        merge_job.execute()

    def _get_single_job(self, project, merge_request, repo, config, options):
        return single_merge_job.SingleMergeJob(
            api=self._api,
            user=self.user,
            project=project,
            merge_request=merge_request,
            repo=repo,
            config=config,
            options=options,
        )


class BotConfig(namedtuple('BotConfig',
                           'user use_https auth_token ssh_key_file project_regexp merge_order merge_opts '
                           + 'git_timeout git_reference_repo batch cli '
                           + 'use_only_gitlab_api')):
    pass


MergeJobOptions = job.MergeJobOptions
Fusion = job.Fusion
