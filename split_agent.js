const { Project } = require('ts-morph');
const fs = require('fs');
const path = require('path');

const project = new Project();
const sourceFile = project.addSourceFileAtPath('web/src/types/agent.ts');

const mappings = {
  core: [
    'ConversationStatus', 'MessageRole', 'MessageType', 'ExecutionStatus', 
    'ThoughtLevel', 'PlanStatus', 'ToolCall', 'ToolResult', 'ArtifactReference', 
    'Message', 'Conversation', 'PaginatedConversationsResponse', 'AgentExecution',
    'AgentExecutionWithDetails', 'ExecutionHistoryResponse', 'ExecutionStatsResponse',
    'ToolExecutionRecord', 'ToolExecutionsResponse', 'DisplayMode',
    'CreateConversationRequest', 'CreateConversationResponse', 'ChatRequest',
    'ToolInfo', 'ToolsListResponse', 'ConversationMessagesResponse'
  ],
  tasks: [
    'TaskStatus', 'TaskPriority', 'AgentTask',
    'HITLRequestType', 'HITLRequestStatus', 'PendingHITLRequest', 'PendingHITLResponse',
    'PlanStep', 'WorkPlan'
  ],
  events: [
    'AgentEventType', 'AgentEvent',
    'MessageEventData', 'ThoughtEventData', 'WorkPlanEventData', 'ActEventData',
    'ActDeltaEventData', 'ObserveEventData', 'CompleteEventData', 'ErrorEventData',
    'RetryEventData', 'TitleGeneratedEventData', 'ClarificationType', 'ClarificationOption',
    'ClarificationAskedEventData', 'ClarificationAnsweredEventData', 'DecisionType',
    'DecisionOption', 'DecisionAskedEventData', 'DecisionAnsweredEventData',
    'EnvVarInputType', 'EnvVarField', 'EnvVarRequestedEventData', 'EnvVarProvidedEventData',
    'DoomLoopDetectedEventData', 'DoomLoopIntervenedEventData', 'PermissionAskedEventData',
    'PermissionRepliedEventData', 'CostUpdateEventData', 'PlanStatusChangedEventData',
    'PlanStepReadyEventData', 'PlanStepCompleteEventData', 'PlanStepSkippedEventData',
    'PlanSnapshotCreatedEventData', 'PlanRollbackEventData', 'AdjustmentAppliedEventData',
    'SandboxEventData', 'ThoughtDeltaEventData', 'TextDeltaEventData', 'TextEndEventData',
    'MemoryRecalledEventData', 'MemoryCapturedEventData', 'PatternMatchEventData',
    'SkillExecutionMode', 'SkillMatchedEventData', 'SkillExecutionStartEventData',
    'SkillToolStartEventData', 'SkillToolResultEventData', 'SkillToolExecution',
    'SkillExecutionCompleteEventData', 'SkillFallbackEventData', 'ContextCompressedEventData',
    'ContextStatusEventData', 'SkillExecutionState', 'TaskListUpdatedEventData',
    'TaskUpdatedEventData', 'TaskStartEventData', 'TaskCompleteEventData',
    'ExecutionPathDecidedEventData', 'SelectionTraceStageData', 'SelectionTraceEventData',
    'PolicyFilteredEventData', 'ToolsetRefreshStatus', 'ToolsetChangedEventData',
    'ExecutionNarrativeStage', 'ExecutionNarrativeEntry',
    'DesktopStartedEventData', 'DesktopStoppedEventData', 'DesktopStatusEventData',
    'TerminalStartedEventData', 'TerminalStoppedEventData', 'TerminalStatusEventData',
    'ScreenshotUpdateEventData', 'SandboxCreatedEventData', 'SandboxTerminatedEventData',
    'SandboxStatusEventData', 'ArtifactCreatedEventData', 'ArtifactReadyEventData',
    'ArtifactErrorEventData', 'ArtifactInfo', 'ArtifactsBatchEventData', 'SuggestionsEventData',
    'ArtifactOpenEventData', 'ArtifactUpdateEventData', 'ArtifactCloseEventData',
    'PlanExecutionStartEvent', 'PlanExecutionCompleteEvent', 'PlanStepReadyEvent',
    'PlanStepCompleteEvent', 'PlanStepSkippedEvent', 'PlanSnapshotCreatedEvent',
    'PlanRollbackEvent', 'ReflectionCompleteEvent', 'AdjustmentAppliedEvent', 'PlanModeEvent',
    'SubAgentRoutedEventData', 'SubAgentStartedEventData', 'SubAgentCompletedEventData',
    'SubAgentFailedEventData', 'SubAgentRunEventData', 'SubAgentSessionSpawnedEventData',
    'SubAgentSessionMessageSentEventData', 'SubAgentAnnounceRetryEventData',
    'SubAgentAnnounceGiveupEventData', 'ParallelStartedEventData', 'ParallelCompletedEventData',
    'ChainStartedEventData', 'ChainStepStartedEventData', 'ChainStepCompletedEventData',
    'ChainCompletedEventData', 'BackgroundLaunchedEventData'
  ],
  timeline: [
    'ToolExecutionStatus', 'TimelineStepStatus', 'ToolExecution', 'TimelineStep',
    'TimelineEventType', 'BaseTimelineEvent', 'UserMessageEvent', 'AssistantMessageEvent',
    'ThoughtEvent', 'ActEvent', 'ObserveEvent', 'WorkPlanTimelineEvent', 'TaskStartTimelineEvent',
    'TaskCompleteTimelineEvent', 'MemoryRecalledTimelineEvent', 'MemoryCapturedTimelineEvent',
    'TextDeltaEvent', 'TextStartEvent', 'TextEndEvent', 'ClarificationAskedTimelineEvent',
    'ClarificationAnsweredTimelineEvent', 'DecisionAskedTimelineEvent', 'DecisionAnsweredTimelineEvent',
    'EnvVarRequestedTimelineEvent', 'EnvVarProvidedTimelineEvent', 'PermissionAskedTimelineEvent',
    'PermissionRequestedTimelineEvent', 'PermissionRepliedTimelineEvent', 'PermissionGrantedTimelineEvent',
    'TimelineEvent', 'SubAgentRoutedTimelineEvent', 'SubAgentStartedTimelineEvent',
    'SubAgentCompletedTimelineEvent', 'SubAgentFailedTimelineEvent', 'ParallelStartedTimelineEvent',
    'ParallelCompletedTimelineEvent', 'ChainStartedTimelineEvent', 'ChainStepStartedTimelineEvent',
    'ChainStepCompletedTimelineEvent', 'ChainCompletedTimelineEvent', 'BackgroundLaunchedTimelineEvent',
    'TimelineResponse', 'DesktopStartedEvent', 'DesktopStoppedEvent', 'DesktopStatusEvent',
    'TerminalStartedEvent', 'TerminalStoppedEvent', 'TerminalStatusEvent', 'ScreenshotUpdateEvent',
    'SandboxCreatedEvent', 'SandboxTerminatedEvent', 'SandboxStatusEvent', 'ArtifactCreatedEvent',
    'ArtifactReadyEvent', 'ArtifactErrorEvent', 'ArtifactsBatchEvent'
  ],
  config: [
    'MCPServerType', 'MCPToolInfo', 'MCPServerResponse', 'MCPServerCreate', 'MCPServerUpdate',
    'MCPServersListResponse', 'MCPServerSyncResponse', 'MCPServerTestResponse',
    'MCPToolCallRequest', 'MCPToolCallResponse', 'StdioTransportConfig', 'HttpTransportConfig',
    'WebSocketTransportConfig', 'ConfigType', 'TenantAgentConfig', 'UpdateTenantAgentConfigRequest',
    'TenantAgentConfigService', 'CommandArgInfo', 'CommandInfo', 'CommandsListResponse', 'SlashItem',
    'DesktopStatus', 'TerminalStatus', 'SandboxStatus', 'LifecycleState', 'LifecycleStateData',
    'SandboxStateData', 'LifecycleStatus', 'ArtifactCategory', 'ArtifactStatus', 'Artifact'
  ],
  workflow: [
    'PatternStep', 'WorkflowPattern', 'PatternsListResponse', 'ResetPatternsResponse',
    'ToolCompositionTemplate', 'ToolComposition', 'ToolCompositionsListResponse',
    'PlanDocumentStatus', 'AgentMode', 'PlanDocument', 'PlanModeStatus', 'EnterPlanModeRequest',
    'ExitPlanModeRequest', 'UpdatePlanRequest', 'ExecutionStepStatus', 'ExecutionPlanStatus',
    'ReflectionAssessment', 'AdjustmentType', 'ExecutionStep', 'StepAdjustment', 'ReflectionResult',
    'StepState', 'PlanSnapshot', 'ExecutionPlan', 'PlanModeEnterEventData', 'PlanModeExitEventData',
    'PlanCreatedEventData', 'PlanUpdatedEventData'
  ],
  execution: [
    'SubAgentTrigger', 'SubAgentResponse', 'SubAgentCreate', 'SubAgentUpdate', 'SubAgentTemplate',
    'SubAgentTemplatesResponse', 'SubAgentsListResponse', 'SubAgentStatsResponse', 'SubAgentMatchResponse',
    'TriggerPattern', 'SkillResponse', 'SkillCreate', 'SkillUpdate', 'SkillsListResponse',
    'SkillMatchResponse', 'SkillContentResponse', 'TenantSkillConfigResponse',
    'TenantSkillConfigListResponse', 'SystemSkillStatus'
  ],
  streaming: [
    'AgentStreamHandler'
  ],
  service: [
    'AgentService'
  ]
};

async function main() {
  const destDir = path.join('web', 'src', 'types', 'agent');
  if (!fs.existsSync(destDir)) {
    fs.mkdirSync(destDir, { recursive: true });
  }

  // Check if anything is missing
  const allKnownNames = new Set(Object.values(mappings).flat());
  const allDecls = sourceFile.getExportedDeclarations();
  
  // Assign unmapped to core
  for (const [name, decls] of allDecls) {
    if (!allKnownNames.has(name)) {
      console.log(`Unmapped export: ${name}, putting in core`);
      mappings.core.push(name);
    }
  }

  const fileContents = {};
  for (const file in mappings) {
    fileContents[file] = [];
  }

  // Iterate over statements in the source file
  const statements = sourceFile.getStatements();
  
  for (const stmt of statements) {
    let name = null;
    if (stmt.getName) {
      name = stmt.getName();
    } else if (stmt.getDeclarations) {
      const decls = stmt.getDeclarations();
      if (decls.length > 0 && decls[0].getName) {
        name = decls[0].getName();
      }
    }
    
    if (!name) continue;
    
    let targetFile = 'core';
    for (const [file, names] of Object.entries(mappings)) {
      if (names.includes(name)) {
        targetFile = file;
        break;
      }
    }
    
    fileContents[targetFile].push(stmt.getFullText());
  }

  for (const [file, contents] of Object.entries(fileContents)) {
    fs.writeFileSync(path.join(destDir, `${file}.ts`), contents.join('\n'));
  }
  
  const indexContent = Object.keys(fileContents).map(file => `export * from './${file}';`).join('\n') + '\n';
  fs.writeFileSync(path.join(destDir, 'index.ts'), indexContent);
  
  console.log("Done splitting types!");
}

main().catch(console.error);
