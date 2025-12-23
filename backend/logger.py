# logger.py
import os
import sys
import logging
import traceback
import functools
from typing import Any, Callable, Optional, Type
from datetime import datetime
import json

# Log levels
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json or text

class StructuredLogger:
    """Structured logging with context"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, LOG_LEVEL))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            if LOG_FORMAT == "json":
                handler.setFormatter(JsonFormatter())
            else:
                handler.setFormatter(
                    logging.Formatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                    )
                )
            self.logger.addHandler(handler)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def _log(self, level: int, message: str, **kwargs):
        extra = {
            "timestamp": datetime.utcnow().isoformat(),
            "context": kwargs
        }
        self.logger.log(level, message, extra=extra)

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logs"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add context if available
        if hasattr(record, 'context') and record.context:
            log_entry["context"] = record.context
        
        # Add exception info if available
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_entry, ensure_ascii=False)

# Custom exceptions
class TechAdvisorError(Exception):
    """Base exception for TechAdvisor"""
    def __init__(self, message: str, context: Optional[dict] = None):
        self.message = message
        self.context = context or {}
        super().__init__(message)

class DatabaseError(TechAdvisorError):
    """Database related errors"""
    pass

class WebSearchError(TechAdvisorError):
    """Web search related errors"""
    pass

class BenchmarkError(TechAdvisorError):
    """Benchmark processing errors"""
    pass

class ValidationError(TechAdvisorError):
    """Data validation errors"""
    pass

# Retry decorator
def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Retry decorator with exponential backoff"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = StructuredLogger(f"retry.{func.__module__}.{func.__name__}")
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"Function failed after {max_attempts} attempts",
                            function=func.__name__,
                            error=str(e),
                            final_attempt=True
                        )
                        raise
                    
                    wait_time = delay * (backoff ** (attempt - 1))
                    logger.warning(
                        f"Attempt {attempt} failed, retrying in {wait_time:.2f}s",
                        function=func.__name__,
                        error=str(e),
                        attempt=attempt,
                        wait_time=wait_time
                    )
                    
                    import time
                    time.sleep(wait_time)
            
            return None  # Should never reach here
        return wrapper
    return decorator

# Error handler decorator
def handle_errors(
    default_return: Any = None,
    reraise: bool = True,
    log_level: str = "error"
):
    """Error handling decorator"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = StructuredLogger(f"error.{func.__module__}.{func.__name__}")
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = {
                    "function": func.__name__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                    "error_type": type(e).__name__
                }
                
                log_method = getattr(logger, log_level.lower())
                log_method(
                    f"Error in {func.__name__}: {str(e)}",
                    **context
                )
                
                if reraise:
                    raise
                return default_return
        
        return wrapper
    return decorator

# Database connection wrapper
def with_db_connection(func: Callable) -> Callable:
    """Database connection management decorator"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from db import get_db_connection
        logger = StructuredLogger(f"db.{func.__name__}")
        
        conn = None
        try:
            conn = get_db_connection()
            if conn is None:
                raise DatabaseError("Could not establish database connection")
            
            # Pass connection as first argument if function expects it
            if 'conn' in func.__code__.co_varnames:
                result = func(conn, *args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            return result
            
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                    logger.debug("Database transaction rolled back")
                except Exception as rollback_error:
                    logger.error(
                        "Failed to rollback transaction",
                        original_error=str(e),
                        rollback_error=str(rollback_error)
                    )
            
            # Re-raise as DatabaseError if it's not already a TechAdvisorError
            if not isinstance(e, TechAdvisorError):
                raise DatabaseError(f"Database operation failed: {str(e)}") from e
            raise
        
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as close_error:
                    logger.warning(f"Failed to close connection: {close_error}")
    
    return wrapper

# Global error handler for FastAPI
def setup_global_error_handler(app):
    """Setup global error handlers for FastAPI"""
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse
    
    logger = StructuredLogger("global.error")
    
    @app.exception_handler(TechAdvisorError)
    async def tech_advisor_error_handler(request: Request, exc: TechAdvisorError):
        logger.error(
            "TechAdvisor error occurred",
            error_type=type(exc).__name__,
            message=exc.message,
            context=exc.context,
            path=request.url.path,
            method=request.method
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": type(exc).__name__,
                "message": exc.message,
                "context": exc.context
            }
        )
    
    @app.exception_handler(Exception)
    async def general_error_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled exception occurred",
            error_type=type(exc).__name__,
            message=str(exc),
            path=request.url.path,
            method=request.method
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred"
            }
        )

# Usage examples and factory function
def get_logger(name: str) -> StructuredLogger:
    """Factory function to get logger instance"""
    return StructuredLogger(name)

# Quick performance monitoring
def monitor_performance(func: Callable) -> Callable:
    """Performance monitoring decorator"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = StructuredLogger(f"perf.{func.__module__}.{func.__name__}")
        
        import time
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.info(
                f"Function completed successfully",
                function=func.__name__,
                duration_ms=round(duration * 1000, 2),
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Function failed",
                function=func.__name__,
                duration_ms=round(duration * 1000, 2),
                error=str(e)
            )
            raise
    
    return wrapper

if __name__ == "__main__":
    # Test the logging system
    logger = get_logger("test")
    
    logger.info("Test info message", user_id=123, action="test")
    logger.warning("Test warning", component="benchmark")
    
    try:
        raise ValueError("Test error")
    except Exception as e:
        logger.error("Test error occurred", error=str(e))
    
    # Test retry decorator
    @retry_on_failure(max_attempts=3, exceptions=(ValueError,))
    def failing_function(fail_count: int = 2):
        if hasattr(failing_function, 'attempts'):
            failing_function.attempts += 1
        else:
            failing_function.attempts = 1
        
        if failing_function.attempts <= fail_count:
            raise ValueError(f"Attempt {failing_function.attempts} failed")
        
        return "Success!"
    
    try:
        result = failing_function(fail_count=2)
        print(f"Retry test result: {result}")
    except Exception as e:
        print(f"Retry test failed: {e}")