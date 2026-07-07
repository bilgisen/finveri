from workers import WorkerEntrypoint
from app.main import create_app
from app.core.d1 import set_db


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        set_db(self.env.DB)
        app = create_app()
        import asgi
        return await asgi.fetch(app, request.js_object, self.env)
