from collections import namedtuple
import json
import logging as log
import requests
from retry import retry


class ApiError(Exception):
    @property
    def error_message(self):
        args = self.args
        if len(args) != 2:
            return None

        arg = args[1]
        if isinstance(arg, dict):
            return arg.get('message')
        return arg


class BadRequest(ApiError):
    pass


class Unauthorized(ApiError):
    pass


class Forbidden(ApiError):
    pass


class NotFound(ApiError):
    pass


class MethodNotAllowed(ApiError):
    pass


class NotAcceptable(ApiError):
    pass


class Conflict(ApiError):
    pass


class Unprocessable(ApiError):
    pass


class InternalServerError(ApiError):
    pass


class TooManyRequests(ApiError):
    pass


class BadGateway(ApiError):
    pass


class ServiceUnavailable(ApiError):
    pass


class GatewayTimeout(ApiError):
    pass


class UnexpectedError(ApiError):
    pass


HTTP_ERRORS = {
    400: BadRequest,
    401: Unauthorized,
    403: Forbidden,
    404: NotFound,
    405: MethodNotAllowed,
    406: NotAcceptable,
    409: Conflict,
    422: Unprocessable,
    429: TooManyRequests,
    500: InternalServerError,
    502: BadGateway,
    503: ServiceUnavailable,
    504: GatewayTimeout,
}


class Api:
    def __init__(self, gitlab_url, auth_token, append_api_version=True):
        self._auth_token = auth_token
        self._api_base_url = gitlab_url.rstrip('/')

        # The `append_api_version` flag facilitates testing.
        if append_api_version:
            self._api_base_url += '/api/v4'

    @retry(
        (requests.exceptions.Timeout,
         Conflict,
         BadGateway,
         ServiceUnavailable,
         InternalServerError,
         TooManyRequests,),
        tries=4,
        delay=20,
        backoff=2,
        jitter=(3, 10,)
    )
    def call(self, command, sudo=None):
        method = command.method
        url = self._api_base_url + command.endpoint

        headers = {'PRIVATE-TOKEN': self._auth_token}

        if sudo:
            headers['SUDO'] = f'{sudo}'
        log.debug('REQUEST: %s %s %r %r', method.__name__.upper(), url, headers, command.call_args)
        try:
            response = method(url, headers=headers, timeout=60, **command.call_args)
        except requests.exceptions.Timeout as err:
            log.error('Request timeout: %s', err)
            raise
        log.debug('RESPONSE CODE: %s', response.status_code)
        log.debug('RESPONSE BODY: %r', response.content)

        if response.status_code == 202:
            return True  # Accepted

        if response.status_code == 204:
            return True  # NoContent

        if response.status_code < 300:
            return command.extract(response.json()) if command.extract else response.json()

        if response.status_code == 304:
            return False  # Not Modified

        def other_error(code, msg):
            exception = InternalServerError if 500 <= code < 600 else UnexpectedError
            return exception(code, msg)

        error = HTTP_ERRORS.get(response.status_code, other_error)
        try:
            err_message = response.json()
        except json.JSONDecodeError:
            log.error('failed to parse error as json from response: %s', response.text)
            err_message = response.reason

        raise error(response.status_code, err_message)

    def collect_all_pages(self, get_command):
        result = []
        fetch_again, page_no = True, 1
        while fetch_again:
            page = self.call(get_command.for_page(page_no))
            if page:
                result.extend(page)
                page_no += 1
            else:
                fetch_again = False

        return result

    def version(self):
        response = self.call(GET('/version'))
        return Version.parse(response['version'])


def from_singleton_list(fun=None):
    fun = fun or (lambda x: x)

    def extractor(response_list):
        assert isinstance(response_list, list), type(response_list)
        assert len(response_list) <= 1, len(response_list)
        if not response_list:
            return None
        return fun(response_list[0])

    return extractor


class Command(namedtuple('Command', 'endpoint args extract')):
    def __new__(cls, endpoint, args=None, extract=None):
        return super(Command, cls).__new__(cls, endpoint, args or {}, extract)

    @property
    def call_args(self):
        return {'json': self.args}


class GET(Command):
    @property
    def method(self):
        return requests.get

    @property
    def call_args(self):
        return {'params': _prepare_params(self.args)}

    def for_page(self, page_no):
        args = self.args
        return self._replace(args=dict(args, page=page_no, per_page=100))


class PUT(Command):
    @property
    def method(self):
        return requests.put


class POST(Command):
    @property
    def method(self):
        return requests.post


class DELETE(Command):
    @property
    def method(self):
        return requests.delete


def _prepare_params(params):
    def process(val):
        if isinstance(val, bool):
            return 'true' if val else 'false'
        return str(val)

    return {key: process(val) for key, val in params.items()}


class Resource:
    def __init__(self, api, info):
        self._info = info
        self._api = api

    @property
    def info(self):
        return self._info

    @property
    def id(self):  # pylint: disable=invalid-name
        return self.info['id']

    @property
    def api(self):
        return self._api

    def __repr__(self):
        return f'{self.__class__.__name__}({self._api}, {self.info})'


class Version(namedtuple('Version', 'release edition')):
    @classmethod
    def parse(cls, string):
        maybe_split_string = string.split('-', maxsplit=1)
        if len(maybe_split_string) == 2:
            release_string, edition = maybe_split_string
        else:
            release_string, edition = string, None

        release = tuple(int(number) for number in release_string.split('.'))
        return cls(release=release, edition=edition)

    @property
    def is_ee(self):
        return self.edition == 'ee'

    def __str__(self):
        release = '.'.join(map(str, self.release))
        return f'{release}-{self.edition}'
