"""VCF Operations API client stub."""
import httpx
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    vcf_operations_url: str = ""
    vcf_operations_user: str = ""
    vcf_operations_password: str = ""
    class Config:
        env_file = ".env"

class VCFOperationsClient:
    def __init__(self):
        s = Settings()
        self.base_url = s.vcf_operations_url
        self.auth = (s.vcf_operations_user, s.vcf_operations_password)

    async def get_alerts(self, active_only: bool = True) -> list[dict]:
        # async with httpx.AsyncClient(verify=False) as c:
        #     r = await c.get(f"{self.base_url}/api/alerts", auth=self.auth)
        #     return r.json()["alerts"]
        return []  # stub — replace with real call

    async def get_metrics(self, resource_id: str) -> dict:
        return {}  # stub
