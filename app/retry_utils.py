"""
Retry utilities for handling transient errors with exponential backoff
"""
import time
import random
import logging
import socket
from typing import Callable, Type, Tuple, Optional, Any
from functools import wraps
from botocore.exceptions import (
    ClientError,
    ReadTimeoutError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ConnectionClosedError,
    BotoCoreError
)

logger = logging.getLogger(__name__)

# Retryable AWS error codes
RETRYABLE_ERROR_CODES = [
    'ServiceUnavailable',
    'InternalError',
    'RequestTimeout',
    'Throttling',
    'SlowDown',
    'RequestTimeoutException',
    'NoSuchUpload',  # Multipart upload not found (can retry)
    'InvalidUpload',  # Multipart upload invalid (can retry)
]

# Retryable exception types
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    ReadTimeoutError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ConnectionClosedError,
    socket.timeout,
    OSError,  # Network-related OS errors
)

# Non-retryable error codes (permanent failures)
NON_RETRYABLE_ERROR_CODES = [
    'InvalidAccessKeyId',
    'SignatureDoesNotMatch',
    'AccessDenied',
    'NoSuchBucket',
    'InvalidBucketName',
    'InvalidParameterValue',
    'InvalidRequest',
    'MalformedXML',
    'InvalidArgument',
]


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is retryable.
    
    Args:
        error: The exception to check
        
    Returns:
        True if the error is retryable, False otherwise
    """
    # Check exception type
    if isinstance(error, RETRYABLE_EXCEPTIONS):
        return True
    
    # Check boto3/botocore errors
    if isinstance(error, BotoCoreError):
        # Connection/timeout errors are retryable
        if isinstance(error, (ReadTimeoutError, ConnectTimeoutError, 
                             EndpointConnectionError, ConnectionClosedError)):
            return True
    
    # Check ClientError for AWS error codes
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        
        # Non-retryable errors
        if error_code in NON_RETRYABLE_ERROR_CODES:
            return False
        
        # Retryable errors
        if error_code in RETRYABLE_ERROR_CODES:
            return True
        
        # HTTP status codes
        status_code = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
        if status_code >= 500:  # Server errors are retryable
            return True
        if status_code == 429:  # Too Many Requests is retryable
            return True
        if status_code == 408:  # Request Timeout is retryable
            return True
        
        # 4xx errors are generally not retryable (except 429, 408)
        if 400 <= status_code < 500:
            return False
    
    # Check error message for common retryable patterns
    error_msg = str(error).lower()
    retryable_patterns = [
        'timeout',
        'connection',
        'network',
        'temporary',
        'retry',
        'throttl',
        'rate limit',
        'service unavailable',
        'internal error',
    ]
    
    if any(pattern in error_msg for pattern in retryable_patterns):
        return True
    
    # Default: non-retryable if we can't determine
    return False


def exponential_backoff(attempt: int, base: float = 2.0, max_delay: float = 60.0, 
                       jitter: bool = True) -> float:
    """
    Calculate exponential backoff delay with optional jitter.
    
    Args:
        attempt: The current attempt number (0-indexed)
        base: Base seconds for exponential backoff
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter to prevent thundering herd
        
    Returns:
        Delay in seconds before next retry
    """
    # Calculate exponential backoff: base * (2 ^ attempt)
    delay = min(base * (2 ** attempt), max_delay)
    
    # Add jitter: random value between 0 and delay * 0.1
    if jitter:
        jitter_amount = random.uniform(0, delay * 0.1)
        delay += jitter_amount
    
    return delay


def retry_with_backoff(
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    retryable_check: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
    reraise_on_non_retryable: bool = True
):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base seconds for exponential backoff
        max_delay: Maximum delay in seconds
        retryable_check: Custom function to check if error is retryable
        on_retry: Callback function called on each retry (error, attempt, delay)
        reraise_on_non_retryable: If True, raise non-retryable errors immediately
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            retry_check = retryable_check or is_retryable_error
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if error is retryable
                    if not retry_check(e):
                        if reraise_on_non_retryable:
                            logger.error(f"Non-retryable error in {func.__name__}: {e}")
                            raise
                        else:
                            logger.warning(f"Non-retryable error in {func.__name__}: {e}")
                            return None
                    
                    # Check if we've exhausted retries
                    if attempt >= max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts. "
                            f"Last error: {e}"
                        )
                        raise
                    
                    # Calculate backoff delay
                    delay = exponential_backoff(attempt, base_delay, max_delay)
                    
                    # Log retry attempt
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1, delay)
                        except Exception as callback_error:
                            logger.warning(f"Error in retry callback: {callback_error}")
                    
                    # Wait before retry
                    time.sleep(delay)
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__} failed unexpectedly")
        
        return wrapper
    return decorator


class RetryContext:
    """
    Context manager for retry logic with more control.
    
    Usage:
        with RetryContext(max_retries=3) as retry:
            for attempt in retry:
                try:
                    result = do_something()
                    break
                except Exception as e:
                    if not retry.should_retry(e):
                        raise
                    retry.wait()
    """
    
    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        retryable_check: Optional[Callable[[Exception], bool]] = None,
        on_retry: Optional[Callable[[Exception, int, float], None]] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retryable_check = retryable_check or is_retryable_error
        self.on_retry = on_retry
        self.attempt = 0
        self.last_error = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False  # Don't suppress exceptions
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.attempt > self.max_retries:
            raise StopIteration
        attempt = self.attempt
        self.attempt += 1
        return attempt
    
    def should_retry(self, error: Exception) -> bool:
        """Check if error is retryable and we haven't exhausted retries."""
        if self.attempt > self.max_retries:
            return False
        return self.retryable_check(error)
    
    def wait(self, error: Optional[Exception] = None):
        """Wait for backoff delay before next retry."""
        if error:
            self.last_error = error
        
        if self.attempt > self.max_retries:
            return
        
        delay = exponential_backoff(self.attempt - 1, self.base_delay, self.max_delay)
        
        if error:
            logger.warning(
                f"Retry attempt {self.attempt}/{self.max_retries + 1} after error: {error}. "
                f"Waiting {delay:.2f} seconds..."
            )
            
            if self.on_retry:
                try:
                    self.on_retry(error, self.attempt, delay)
                except Exception as callback_error:
                    logger.warning(f"Error in retry callback: {callback_error}")
        
        time.sleep(delay)
