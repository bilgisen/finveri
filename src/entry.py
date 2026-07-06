from workers import WorkerEntrypoint, Response
from app.main import app


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return await app(request, self.env)
