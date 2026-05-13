from types import SimpleNamespace

from app.config import Settings
from app.vllm_client import VoxtralVLLMClient


def test_list_models_uses_openai_compatible_client(tmp_path):
    settings = Settings(project_root=tmp_path)
    client = VoxtralVLLMClient(settings)
    client._client = SimpleNamespace(
        models=SimpleNamespace(
            list=lambda: SimpleNamespace(data=[SimpleNamespace(id="mistralai/Voxtral-Mini-3B-2507")])
        )
    )

    assert client.list_models() == ["mistralai/Voxtral-Mini-3B-2507"]
    assert client.resolve_model() == "mistralai/Voxtral-Mini-3B-2507"

