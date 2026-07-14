# keti-book-studio

도서 편집 및 단위 재계산 API 백엔드.
<img width="792" height="625" alt="image" src="https://github.com/user-attachments/assets/ab56d8b4-76a1-4dc8-a521-6008b62dadc0" />


backend/
├── skills/          # 프롬프트+파싱 순수 함수 
├── orchestration/    # 확정 시퀀스(write→review→revise)
├── chat/
│   ├── adk_agent.py       # ChatRoot
│   └── sub_agents/         # ADK Agent 객체 3개 (Editor/Outline/Writing)
├── api/              # REST
└── storage/          # DB

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 실행

```bash
uvicorn backend.main:app --reload
```

## 테스트

```bash
pytest
```
