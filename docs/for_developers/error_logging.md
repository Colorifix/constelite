# Error logging

To simplify catching and loggin errors, Constelite provies two wrapper functions: `utils.log_exception` and `utils.async_log_exception`.

Both behave the same way:

1. Catch exception in the wrapped function and log it
2. Re-raise the exception.