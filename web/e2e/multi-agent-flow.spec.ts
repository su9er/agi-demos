/**
 * Multi-agent flow e2e (Track B · b-e2e).
 *
 * API-level end-to-end coverage for the participant + HITL backend
 * surfaces shipped in Track B phase-2. Full UI-level coverage
 * (``@mention picker chips``, ``room-HITL accept flow``) depends on
 * wiring ``ConversationParticipantsPanel`` / ``MentionPicker`` /
 * ``HITLCenterPanel`` into ``AgentWorkspace`` — it is captured here
 * as ``test.skip`` placeholders to be enabled once the wiring lands.
 *
 * Scenarios validated (real HTTP, real backend):
 *
 * 1. ``multi_agent_shared`` project creates a conversation whose
 *    effective mode resolves via the project default.
 * 2. ``POST /agent/conversations/{id}/participants`` adds a second
 *    agent; ``GET`` returns the updated roster.
 * 3. ``DELETE`` with a ``reason`` body removes the agent.
 * 4. Pending HITL endpoint responds with an empty list on a fresh
 *    conversation (smoke coverage — pre-b-hitl-policy router).
 * 5. Attempt to add a 2nd participant on a ``single_agent`` project
 *    returns 409 (domain cap enforced over HTTP).
 */

import { test, expect } from './base';

const API_BASE = process.env.API_BASE || 'http://localhost:8000';

interface TokenResponse {
  access_token: string;
  token_type?: string;
}

interface ProjectResponse {
  id: string;
  name: string;
  tenant_id: string;
}

interface ConversationResponse {
  id: string;
  project_id: string;
  tenant_id: string;
  user_id: string;
}

interface RosterResponse {
  conversation_id: string;
  conversation_mode: string;
  effective_mode: string;
  participant_agents: string[];
  coordinator_agent_id: string | null;
  focused_agent_id: string | null;
}

interface PendingHITLResponse {
  requests: unknown[];
  total: number;
}

async function login(): Promise<string> {
  const form = new URLSearchParams();
  form.append('username', 'admin@memstack.ai');
  form.append('password', 'adminpassword');
  const resp = await fetch(`${API_BASE}/api/v1/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });
  expect(resp.ok).toBeTruthy();
  const data = (await resp.json()) as TokenResponse;
  return data.access_token;
}

async function pickTenantId(token: string): Promise<string> {
  const resp = await fetch(`${API_BASE}/api/v1/tenants`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(resp.ok).toBeTruthy();
  const data = (await resp.json()) as { tenants?: Array<{ id: string }> } | Array<{ id: string }>;
  const tenants = Array.isArray(data) ? data : data.tenants || [];
  expect(tenants.length).toBeGreaterThan(0);
  return tenants[0].id;
}

async function createProject(
  token: string,
  tenantId: string,
  conversationMode: string
): Promise<ProjectResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/projects/`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      name: `Playwright E2E Test ${Date.now()}`,
      description: 'Multi-agent flow e2e project',
      tenant_id: tenantId,
      agent_conversation_mode: conversationMode,
    }),
  });
  expect(resp.ok, `createProject failed: ${resp.status} ${await resp.text()}`).toBeTruthy();
  return (await resp.json()) as ProjectResponse;
}

async function createConversation(
  token: string,
  projectId: string
): Promise<ConversationResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/agent/conversations`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      project_id: projectId,
      title: 'E2E multi-agent conversation',
    }),
  });
  expect(
    resp.ok,
    `createConversation failed: ${resp.status} ${await resp.text()}`
  ).toBeTruthy();
  return (await resp.json()) as ConversationResponse;
}

async function authedFetch(
  token: string,
  method: string,
  path: string,
  body?: unknown
): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

test.describe('multi-agent conversation flow (API)', () => {
  test('roster add/list/remove round-trip on a shared-mode project', async () => {
    const token = await login();
    const tenantId = await pickTenantId(token);
    const project = await createProject(token, tenantId, 'multi_agent_shared');
    const conversation = await createConversation(token, project.id);

    // Initial roster — single_agent mode inherits empty roster initially,
    // but effective mode should reflect the project setting.
    const initialResp = await authedFetch(
      token,
      'GET',
      `/api/v1/agent/conversations/${conversation.id}/participants`
    );
    expect(initialResp.ok).toBeTruthy();
    const initial = (await initialResp.json()) as RosterResponse;
    expect(initial.effective_mode).toBe('multi_agent_shared');

    // Add agent-alpha
    const addResp = await authedFetch(
      token,
      'POST',
      `/api/v1/agent/conversations/${conversation.id}/participants`,
      { agent_id: 'agent-alpha', role: 'reviewer' }
    );
    expect(
      addResp.ok,
      `add participant failed: ${addResp.status} ${await addResp.text()}`
    ).toBeTruthy();
    const withOne = (await addResp.json()) as RosterResponse;
    expect(withOne.participant_agents).toContain('agent-alpha');

    // Add agent-beta
    const addResp2 = await authedFetch(
      token,
      'POST',
      `/api/v1/agent/conversations/${conversation.id}/participants`,
      { agent_id: 'agent-beta' }
    );
    expect(addResp2.ok).toBeTruthy();
    const withTwo = (await addResp2.json()) as RosterResponse;
    expect(withTwo.participant_agents).toEqual(
      expect.arrayContaining(['agent-alpha', 'agent-beta'])
    );

    // GET list and confirm it matches
    const listResp = await authedFetch(
      token,
      'GET',
      `/api/v1/agent/conversations/${conversation.id}/participants`
    );
    expect(listResp.ok).toBeTruthy();
    const list = (await listResp.json()) as RosterResponse;
    expect(list.participant_agents).toEqual(
      expect.arrayContaining(['agent-alpha', 'agent-beta'])
    );

    // DELETE with reason
    const removeResp = await authedFetch(
      token,
      'DELETE',
      `/api/v1/agent/conversations/${conversation.id}/participants/agent-beta`,
      { reason: 'Reassigned to another task' }
    );
    expect(removeResp.ok).toBeTruthy();
    const afterRemove = (await removeResp.json()) as RosterResponse;
    expect(afterRemove.participant_agents).not.toContain('agent-beta');
    expect(afterRemove.participant_agents).toContain('agent-alpha');
  });

  test('single_agent project rejects a second participant with 409', async () => {
    const token = await login();
    const tenantId = await pickTenantId(token);
    const project = await createProject(token, tenantId, 'single_agent');
    const conversation = await createConversation(token, project.id);

    // First add should succeed.
    const first = await authedFetch(
      token,
      'POST',
      `/api/v1/agent/conversations/${conversation.id}/participants`,
      { agent_id: 'agent-solo' }
    );
    expect(first.ok).toBeTruthy();

    // Second add violates the single_agent cap.
    const second = await authedFetch(
      token,
      'POST',
      `/api/v1/agent/conversations/${conversation.id}/participants`,
      { agent_id: 'agent-intruder' }
    );
    expect(second.status).toBe(409);
  });

  test('pending HITL endpoint returns an empty list for a fresh conversation', async () => {
    const token = await login();
    const tenantId = await pickTenantId(token);
    const project = await createProject(token, tenantId, 'multi_agent_shared');
    const conversation = await createConversation(token, project.id);

    const resp = await authedFetch(
      token,
      'GET',
      `/api/v1/agent/hitl/conversations/${conversation.id}/pending`
    );
    expect(resp.ok).toBeTruthy();
    const pending = (await resp.json()) as PendingHITLResponse;
    expect(pending.total).toBe(0);
    expect(pending.requests).toEqual([]);
  });
});

test.describe('multi-agent UI flows (requires panel wiring)', () => {
  // These scenarios are part of b-e2e's charter but depend on
  // ConversationParticipantsPanel / MentionPicker / HITLCenterPanel
  // being mounted in AgentWorkspace. Enable once the wiring PR lands.

  test.skip('autonomous scenario: goal → WS disconnect → reconnect → finished event', () => {
    // TODO: wire panels + autonomous mode UI.
  });

  test.skip('shared-mode @mention via picker inserts chip and routes by set membership', () => {
    // TODO: wire MentionPicker into the message input component.
  });

  test.skip('room-HITL accept flow resolves pending request from HITLCenterPanel', () => {
    // TODO: wire HITLCenterPanel resolve action once policy-table router exists.
  });
});
