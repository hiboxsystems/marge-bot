import logging

from marge import bot
from marge.job import Fusion

# reduce noise, see: https://github.com/eisensheng/pytest-catchlog/issues/59
logging.getLogger('flake8').propagate = False


def create_bot_config(user, options):
    return bot.BotConfig(
        user=user,
        use_only_gitlab_api=options.fusion is Fusion.gitlab_rebase,
        use_https=False,
        auth_token='',
        ssh_key_file='',
        project_regexp='',
        git_timeout='',
        git_reference_repo='',
        merge_order='created_at',
        merge_opts=options,
        batch=False,
        cli=False,
    )
