"""Sanitized exception hierarchy.

Every exception message in this project is safe to log and safe to show a reviewer.
Secrets, credentials and raw customer message bodies never appear in exception text.
"""
from __future__ import annotations


class SupportScoutError(Exception):
    """Base class for every expected SupportScout failure."""

    #: Stable machine-readable category used by the error audit log.
    category = "support_scout_error"
    #: Whether retrying the same operation could plausibly succeed.
    retryable = False


class ConfigurationError(SupportScoutError):
    category = "configuration_error"


class FileOutputError(SupportScoutError):
    category = "file_output_error"


class ModelClientError(SupportScoutError):
    category = "model_client_error"


class ModelAuthenticationError(ModelClientError):
    category = "model_authentication_error"


class ModelTimeoutError(ModelClientError):
    category = "model_timeout_error"
    retryable = True


class ModelTransportError(ModelClientError):
    category = "model_transport_error"
    retryable = True


class ModelResponseError(ModelClientError):
    category = "model_response_error"
    retryable = True


class SearchError(SupportScoutError):
    category = "search_error"


class SearchAuthenticationError(SearchError):
    category = "search_authentication_error"


class SearchTimeoutError(SearchError):
    category = "search_timeout_error"
    retryable = True


class SearchResponseError(SearchError):
    category = "search_response_error"


class ScrapeError(SupportScoutError):
    category = "scrape_error"


class ScrapeTimeoutError(ScrapeError):
    category = "scrape_timeout_error"
    retryable = True


class ScrapeSizeError(ScrapeError):
    category = "scrape_size_error"


class ScrapeContentTypeError(ScrapeError):
    category = "scrape_content_type_error"


class UnsafeURLError(SupportScoutError):
    category = "unsafe_url_error"


class SupportDataClientError(SupportScoutError):
    category = "support_data_client_error"
    retryable = True


class SupportDataNotFound(SupportDataClientError):
    category = "support_data_not_found"
    retryable = False


class WorkflowError(SupportScoutError):
    category = "workflow_error"


class ExecutionBudgetExceeded(SupportScoutError):
    category = "execution_budget_exceeded"
