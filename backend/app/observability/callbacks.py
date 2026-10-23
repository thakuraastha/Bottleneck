from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

from google.adk.agents.context import Context
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.tables import AgentRunRow, SecurityEventRow
from app.security import GuardrailService, GuardrailViolation


class AdkObservabilityCallbacks:
    """Persist supported ADK lifecycle callbacks as truthful execution events."""

    def __init__(self, sessions: sessionmaker[Session], *, model_identifier: str) -> None:
        self._sessions = sessions
        self._model_identifier = model_identifier
        self._active_agents: dict[tuple[str, str], str] = {}
        self._active_tools: dict[tuple[str, str], str] = {}
        self._lock = Lock()

    @staticmethod
    def _scope(context: Context) -> tuple[str | None, str | None]:
        return context.state.get("incident_id"), context.state.get("workflow_run_id")

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _tool_key(context: Context, tool: BaseTool) -> tuple[str, str]:
        return context.invocation_id, context.function_call_id or tool.name

    def _insert(self, context: Context, *, execution_id: str, tool_name: str | None = None) -> bool:
        incident_id, workflow_run_id = self._scope(context)
        if not incident_id or not workflow_run_id:
            return False
        with self._sessions() as session:
            retry_count = max(context.attempt_count - 1, 0)
            if tool_name is None:
                prior_attempts = session.scalar(
                    select(func.count())
                    .select_from(AgentRunRow)
                    .where(
                        AgentRunRow.workflow_run_id == workflow_run_id,
                        AgentRunRow.agent_name == context.agent_name,
                        AgentRunRow.tool_name.is_(None),
                    )
                ) or 0
                retry_count = max(retry_count, prior_attempts)
            session.add(
                AgentRunRow(
                    execution_id=execution_id,
                    incident_id=incident_id,
                    workflow_run_id=workflow_run_id,
                    agent_name=context.agent_name,
                    tool_name=tool_name,
                    start_time=self._now(),
                    status="RUNNING",
                    retry_count=retry_count,
                    model_identifier=self._model_identifier,
                )
            )
            session.commit()
        return True

    def _finish(
        self,
        execution_id: str | None,
        *,
        status: str,
        error: Exception | None = None,
        model_identifier: str | None = None,
        token_usage: dict[str, Any] | None = None,
    ) -> None:
        if not execution_id:
            return
        now = self._now()
        with self._sessions() as session:
            row = session.get(AgentRunRow, execution_id)
            if row is None:
                return
            row.end_time = now
            started_at = row.start_time
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            row.duration_ms = max((now - started_at).total_seconds() * 1000, 0.0)
            row.status = status
            row.error = str(error) if error else None
            row.model_identifier = model_identifier or row.model_identifier
            row.token_usage = token_usage or row.token_usage
            session.commit()

    def _record_security(
        self,
        context: Context,
        *,
        stage: str,
        violation: GuardrailViolation,
    ) -> None:
        incident_id, workflow_run_id = self._scope(context)
        with self._sessions() as session:
            session.add(
                SecurityEventRow(
                    security_event_id=str(uuid4()),
                    incident_id=incident_id,
                    workflow_run_id=workflow_run_id,
                    stage=stage,
                    outcome="BLOCKED",
                    rule=violation.result.rule,
                    detail=violation.result.detail,
                    created_at=self._now(),
                )
            )
            session.commit()

    def before_agent(self, context: Context) -> None:
        execution_id = str(uuid4())
        if self._insert(context, execution_id=execution_id):
            with self._lock:
                self._active_agents[(context.invocation_id, context.agent_name)] = execution_id

    def after_agent(self, context: Context) -> None:
        key = (context.invocation_id, context.agent_name)
        with self._lock:
            execution_id = self._active_agents.pop(key, None)
        self._finish(execution_id, status="COMPLETED")

    @staticmethod
    def _model_request_text(request: LlmRequest) -> str:
        """Extract prompt text without serializing ADK schema classes or tool objects."""
        fragments: list[str] = []
        for content in request.contents or []:
            for part in getattr(content, "parts", None) or []:
                value = getattr(part, "text", None)
                if isinstance(value, str):
                    fragments.append(value)

        config = getattr(request, "config", None)
        system_instruction = getattr(config, "system_instruction", None)
        if isinstance(system_instruction, str):
            fragments.append(system_instruction)
        elif system_instruction is not None:
            for part in getattr(system_instruction, "parts", None) or []:
                value = getattr(part, "text", None)
                if isinstance(value, str):
                    fragments.append(value)
        return "\n".join(fragments)

    def before_model(self, context: Context, request: LlmRequest) -> None:
        try:
            GuardrailService.require_safe_text(self._model_request_text(request))
        except GuardrailViolation as exc:
            self._record_security(context, stage="before_model", violation=exc)
            raise

    def after_model(self, context: Context, response: LlmResponse) -> None:
        key = (context.invocation_id, context.agent_name)
        with self._lock:
            execution_id = self._active_agents.get(key)
        usage = response.usage_metadata.model_dump(mode="json", exclude_none=True) if response.usage_metadata else None
        if execution_id and (usage or response.model_version):
            with self._sessions() as session:
                row = session.get(AgentRunRow, execution_id)
                if row:
                    row.model_identifier = response.model_version or row.model_identifier
                    row.token_usage = usage or row.token_usage
                    session.commit()

    def on_model_error(self, context: Context, request: LlmRequest, error: Exception) -> None:
        key = (context.invocation_id, context.agent_name)
        with self._lock:
            execution_id = self._active_agents.pop(key, None)
        self._finish(execution_id, status="FAILED", error=error)

    def before_tool(self, tool: BaseTool, args: dict[str, Any], context: Context) -> None:
        try:
            GuardrailService.require_valid_tool_payload(args)
        except GuardrailViolation as exc:
            self._record_security(context, stage="before_tool", violation=exc)
            raise
        execution_id = str(uuid4())
        if self._insert(context, execution_id=execution_id, tool_name=tool.name):
            with self._lock:
                self._active_tools[self._tool_key(context, tool)] = execution_id

    def after_tool(
        self,
        tool: BaseTool,
        args: dict[str, Any],
        context: Context,
        tool_response: dict[str, Any],
    ) -> None:
        try:
            GuardrailService.require_valid_tool_payload(tool_response)
        except GuardrailViolation as exc:
            self._record_security(context, stage="after_tool", violation=exc)
            raise
        with self._lock:
            execution_id = self._active_tools.pop(self._tool_key(context, tool), None)
        self._finish(execution_id, status="COMPLETED")

    def on_tool_error(
        self,
        tool: BaseTool,
        args: dict[str, Any],
        context: Context,
        error: Exception,
    ) -> None:
        with self._lock:
            execution_id = self._active_tools.pop(self._tool_key(context, tool), None)
        self._finish(execution_id, status="FAILED", error=error)

    def fail_open_runs(self, error: Exception) -> None:
        """Close callback records when ADK aborts outside its error callbacks."""
        with self._lock:
            execution_ids = [
                *self._active_agents.values(),
                *self._active_tools.values(),
            ]
            self._active_agents.clear()
            self._active_tools.clear()
        for execution_id in execution_ids:
            self._finish(execution_id, status="FAILED", error=error)

    def agent_kwargs(self) -> dict[str, Any]:
        """Return callback wiring accepted by maintained ADK LlmAgent releases."""
        return {
            "before_agent_callback": self.before_agent,
            "after_agent_callback": self.after_agent,
            "before_model_callback": self.before_model,
            "after_model_callback": self.after_model,
            "on_model_error_callback": self.on_model_error,
            "before_tool_callback": self.before_tool,
            "after_tool_callback": self.after_tool,
            "on_tool_error_callback": self.on_tool_error,
        }
