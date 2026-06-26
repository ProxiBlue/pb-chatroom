"""pb-chatroom REST API routers."""

from .threads import router as threads_router

__all__ = ['threads_router']
