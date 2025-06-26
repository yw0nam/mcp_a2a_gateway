# a2a_mcp_server/agent_manager.py (수정됨)
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import httpx
import logging

from a2a.client import A2ACardResolver
from a2a.types import AgentCard

logger = logging.getLogger(__name__)


class AgentInfo(BaseModel):
    """
    A2A 에이전트의 AgentCard만 저장합니다.
    URL은 이 객체를 저장하는 딕셔너리의 키로 사용됩니다.
    """

    card: AgentCard = Field(description="The full AgentCard of the agent")

    class Config:
        arbitrary_types_allowed = True


class AgentManager:
    def __init__(self):
        self.registered_agents: Dict[str, AgentInfo] = {}

    async def register_agent(self, url: str) -> Tuple[str, AgentInfo]:
        """A2ACardResolver를 사용하여 AgentCard를 가져오고 에이전트를 등록합니다."""
        try:
            async with httpx.AsyncClient() as http_client:
                resolver = A2ACardResolver(httpx_client=http_client, base_url=url)
                agent_card = await resolver.get_agent_card()

            # url 필드 없이 AgentInfo 객체 생성
            agent_info = AgentInfo(card=agent_card)
            self.registered_agents[url] = agent_info
            logger.info(f"Successfully registered agent: {agent_card.name}")
            return url, agent_info
        except Exception as e:
            logger.error(f"Failed to register agent at {url}: {e}")
            raise

    def unregister_agent(self, url: str) -> Optional[AgentInfo]:
        """에이전트 등록을 해제합니다."""
        if url in self.registered_agents:
            agent_info = self.registered_agents.pop(url)
            logger.info(f"Successfully unregistered agent: {agent_info.card.name}")
            return agent_info
        return None

    def get_agent(self, url: str) -> Optional[AgentInfo]:
        """특정 에이전트 정보를 가져옵니다."""
        return self.registered_agents.get(url)

    def list_agents_with_url(self) -> List[Tuple[str, AgentInfo]]:
        """URL과 함께 모든 등록된 에이전트 목록을 반환합니다."""
        return list(self.registered_agents.items())

    def get_agents_data_for_saving(self) -> Dict[str, dict]:
        """저장을 위해 직렬화된 에이전트 데이터를 반환합니다."""
        return {
            url: agent.model_dump(mode="json")
            for url, agent in self.registered_agents.items()
        }

    def load_agents_from_data(self, data: Dict[str, dict]):
        """파일에서 에이전트 데이터를 불러옵니다."""
        for url, agent_data in data.items():
            try:
                # dict에서 AgentInfo 객체를 생성합니다 (이제 url 필드가 없습니다).
                self.registered_agents[url] = AgentInfo.model_validate(agent_data)
            except Exception as e:
                logger.error(f"Failed to load agent data for {url}: {e}")
        logger.info(f"Loaded {len(self.registered_agents)} agents.")
