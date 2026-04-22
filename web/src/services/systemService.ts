import { httpClient } from './client/httpClient';

export interface SystemInfoResponse {
  edition: string;
  features: Array<Record<string, unknown>>;
  agent_runtime: {
    mode: string;
  };
  memory_runtime: {
    mode: string;
    failure_persistence_enabled: boolean;
  };
}

class SystemService {
  async getInfo(): Promise<SystemInfoResponse> {
    return await httpClient.get<SystemInfoResponse>('/system/info');
  }
}

export const systemService = new SystemService();

export default systemService;
