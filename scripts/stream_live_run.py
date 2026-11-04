#!/usr/bin/env python3
import time
import sys
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"
INCIDENT_ID = "INC-DEMO"

def get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))

def post_json(url, payload=None):
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

def main():
    print("=" * 72)
    print("  BOTTLENECK LIVE MULTI-AGENT ORCHESTRATION STREAM")
    print("=" * 72)
    print(f"Connecting to API at {BASE_URL}...")
    
    try:
        health = get_json(f"{BASE_URL}/health")
        print(f"✓ Backend health status: {health.get('status')}")
    except Exception as e:
        print(f"✗ Failed to connect to API: {e}")
        sys.exit(1)

    print(f"\n[1/3] Triggering live workflow for incident: {INCIDENT_ID}")
    try:
        run_init = post_json(f"{BASE_URL}/incidents/{INCIDENT_ID}/run")
        run_id = run_init.get("workflow_run_id")
        print(f"✓ Started Workflow Run ID: {run_id}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"✗ API returned {e.code}: {err_body}")
        # If already running or completed, let's grab the latest run id
        wf = get_json(f"{BASE_URL}/incidents/{INCIDENT_ID}/workflow")
        run_id = wf.get("workflow_runs", [{}])[-1].get("workflow_run_id")
        print(f"-> Tracking existing Run ID: {run_id}")

    print("\n[2/3] Streaming live agent events and state transitions...")
    print("-" * 72)

    seen_agents = set()
    last_phase = None
    last_progress = None
    completed = False
    start_time = time.time()

    while not completed and (time.time() - start_time < 90):
        try:
            wf_data = get_json(f"{BASE_URL}/incidents/{INCIDENT_ID}/workflow")
            runs = wf_data.get("workflow_runs", [])
            current_run = next((r for r in runs if r.get("workflow_run_id") == run_id), None)
            
            if current_run:
                st = current_run.get("state") or {}
                phase = st.get("phase")
                phase_label = st.get("phase_label")
                progress = st.get("progress_percent", 0)
                status = current_run.get("status")

                if (phase != last_phase) or (progress != last_progress):
                    print(f"\n⚡ [PHASE {progress}%] {phase_label or phase} (Status: {status})")
                    last_phase = phase
                    last_progress = progress

                if status in ("COMPLETED", "FAILED"):
                    completed = True

            # Check new agent executions for this workflow
            agent_runs = wf_data.get("agent_runs", [])
            for agent in agent_runs:
                if agent.get("workflow_run_id") != run_id:
                    continue
                exec_id = agent.get("execution_id")
                if exec_id in seen_agents:
                    continue
                seen_agents.add(exec_id)

                agent_name = agent.get("agent_name")
                tool_name = agent.get("tool_name")
                duration = agent.get("duration_ms")
                astatus = agent.get("status")
                model = agent.get("model_identifier") or "system"
                tokens = agent.get("token_usage") or {}
                total_tokens = tokens.get("total_token_count")

                token_str = f" | {total_tokens} tokens" if total_tokens else ""
                dur_str = f" in {duration:.1f}ms" if duration is not None else ""
                
                if tool_name:
                    print(f"   🔧 TOOL CALL [{astatus}] {agent_name} -> {tool_name}{dur_str}")
                else:
                    icon = "✓" if astatus == "COMPLETED" else "✗"
                    print(f"   🤖 AGENT [{astatus}] {agent_name} ({model}{token_str}){dur_str}")

            time.sleep(0.8)
        except Exception as e:
            print(f"   [poll error]: {e}")
            time.sleep(1)

    print("-" * 72)
    print("\n[3/3] Fetching final incident resolution & audit summary...")
    try:
        audit = get_json(f"{BASE_URL}/incidents/{INCIDENT_ID}/audit")
        report = get_json(f"{BASE_URL}/incidents/{INCIDENT_ID}/report")
        
        risk = report.get("risk_assessment") or {}
        strategies = report.get("strategies") or []
        plan = report.get("execution_plan")
        incident = report.get("incident") or {}

        print(f"\n📋 INCIDENT SUMMARY:")
        print(f"   • Incident ID:    {incident.get('incident_id')}")
        print(f"   • Title:          {incident.get('title')}")
        print(f"   • Component:      {incident.get('component_id')}")
        print(f"   • Current Status: {incident.get('status')}")

        print(f"\n⚠️  DETERMINISTIC RISK ASSESSMENT:")
        print(f"   • Severity:       {risk.get('severity')}")
        print(f"   • Financial Risk: ${risk.get('financial_risk_usd', 0):,.2f}")
        print(f"   • Days to Stock:  {risk.get('days_to_stockout')} days")
        print(f"   • Summary:        {risk.get('risk_summary')}")

        print(f"\n💡 PROPOSED RECOVERY STRATEGIES ({len(strategies)} found):")
        for i, s in enumerate(strategies, 1):
            is_rec = " ⭐ [RECOMMENDED]" if s.get("strategy_id") == (plan or {}).get("strategy_id") else ""
            print(f"   {i}. [{s.get('strategy_type')}] {s.get('name')}{is_rec}")
            print(f"      - Net Impact Cost: ${s.get('estimated_cost_usd', 0):,.2f}")
            print(f"      - Feasibility:     {s.get('feasibility_score')}/100")
            print(f"      - Rationale:       {s.get('description')}")

        reflections = audit.get("reflections") or []
        if reflections:
            latest_ref = reflections[-1]
            print(f"\n🔍 REFLECTION QUALITY GATE:")
            print(f"   • Passed:          {latest_ref.get('passed')}")
            print(f"   • Quality Score:   {latest_ref.get('quality_score')}")
            issues = (latest_ref.get('result_data') or {}).get('issues', [])
            if issues:
                print(f"   • Notes:           {', '.join(issues)}")
            else:
                print(f"   • Verification:    All constraints, evidence provenance & calculations verified.")

        print(f"\n🛡️  STATUS: WAITING_FOR_HUMAN_APPROVAL")
        print("=" * 72)
    except Exception as e:
        print(f"Could not load final audit report: {e}")

if __name__ == "__main__":
    main()
