# -*- coding: utf-8 -*-
# Revised by Kera (GPT-6 Astra): 2026-11-13 (optional page selection).

from enum import Enum

from wallabag.api.api import Api, ApiMethod, ValueException


class Params(Enum):
    COUNT = "count"
    FILTER_READ = "filter_read"
    FILTER_STARRED = "filter_starred"
    OLDEST = "oldest"
    TAGS = "tags"
    PAGE = "page"


class GetListEntries(Api):

    API_METHOD = ApiMethod.LIST_ENTRIES

    class ApiParams(Enum):
        PER_PAGE = "perPage"
        ORDER = "order"
        ARCHIVE = "archive"
        STARRED = "starred"
        TAGS = "tags"
        DETAIL = "detail"
        PAGE = "page"

    class ApiValues():
        class ORDER(Enum):
            ASC = "asc"

        class DETAIL(Enum):
            META = "metadata"
            FULL = "full"

    def __init__(self, config, params):
        Api.__init__(self, config)
        self.params = params

    def _make_request(self, request):
        return self._request_get(request)

    def _get_api_url(self):
        return self._build_url(GetListEntries.API_METHOD)

    def _get_params(self):
        ApiParams = self.ApiParams
        ApiValues = self.ApiValues
        count = self.__get_count(self.params[Params.COUNT])
        api_params = {
            ApiParams.PER_PAGE.value: count,
            ApiParams.DETAIL.value: ApiValues.DETAIL.META.value
        }

        if Params.PAGE in self.params:
            page = self.params[Params.PAGE]
            if type(page) is not int or page < 1:
                raise ValueException("Page must be a positive integer")
            api_params[ApiParams.PAGE.value] = page

        if Params.OLDEST in self.params and self.params[Params.OLDEST]:
            api_params[ApiParams.ORDER.value] = ApiValues.ORDER.ASC.value

        if Params.FILTER_READ in self.params:
            self._put_bool_param(
                    api_params, Params.FILTER_READ, ApiParams.ARCHIVE)

        if Params.FILTER_STARRED in self.params:
            self._put_bool_param(
                    api_params, Params.FILTER_STARRED, ApiParams.STARRED)

        if Params.TAGS in self.params:
            api_params[ApiParams.TAGS.value] = self.params[Params.TAGS]

        return api_params

    def __get_count(self, count):
        return 0 if not count or count < 0 else count
