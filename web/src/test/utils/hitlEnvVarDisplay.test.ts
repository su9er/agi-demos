import { describe, expect, it } from 'vitest';

import {
  decodeEnvVarRequestedEventData,
  decodeHtmlEntities,
  decodeUnifiedEnvVarRequestData,
} from '../../utils/hitlEnvVarDisplay';

describe('hitlEnvVarDisplay', () => {
  it('decodes one layer of HTML entities', () => {
    expect(decodeHtmlEntities('A&amp;B')).toBe('A&B');
    expect(decodeHtmlEntities('sk&amp;#45;123456')).toBe('sk&#45;123456');
    expect(decodeHtmlEntities('bad&#99999999;entity')).toBe('bad&#99999999;entity');
  });

  it('decodes snake_case env-var request payloads for inline cards', () => {
    const decoded = decodeEnvVarRequestedEventData({
      request_id: 'req-1',
      tool_name: 'web&amp;search',
      message: 'Need Search &amp; Region',
      fields: [
        {
          name: 'SEARCH_REGION',
          label: 'Search &amp; Region',
          required: true,
          input_type: 'text',
          description: 'Use &lt;region&gt;',
          default_value: 'A&amp;B',
          placeholder: 'https://api.example.com?x=1&amp;y=2',
          pattern: 'A&amp;B',
        },
      ],
      context: {
        requested_variables: ['Search &amp; Region'],
        note: 'Use &lt;safe&gt; text',
      },
    });

    expect(decoded.tool_name).toBe('web&search');
    expect(decoded.message).toBe('Need Search & Region');
    expect(decoded.fields[0].label).toBe('Search & Region');
    expect(decoded.fields[0].description).toBe('Use <region>');
    expect(decoded.fields[0].default_value).toBe('A&B');
    expect(decoded.fields[0].placeholder).toBe('https://api.example.com?x=1&y=2');
    expect(decoded.fields[0].pattern).toBe('A&B');
    expect(decoded.context?.requested_variables).toEqual(['Search & Region']);
    expect(decoded.context?.note).toBe('Use <safe> text');
  });

  it('decodes camelCase env-var request payloads for the unified panel', () => {
    const decoded = decodeUnifiedEnvVarRequestData({
      toolName: 'web&amp;search',
      message: 'Need &lt;b&gt;token&lt;/b&gt;',
      allowSave: true,
      fields: [
        {
          name: 'API_KEY',
          label: 'API &amp; Key',
          required: true,
          secret: false,
          inputType: 'text',
          description: 'Paste &lt;token&gt;',
          defaultValue: 'A&amp;B',
          placeholder: 'https://api.example.com?x=1&amp;y=2',
          pattern: 'A&amp;B',
        },
      ],
      context: {
        tool_name: 'web&amp;search',
        requested_variables: ['API &amp; Key'],
      },
    });

    expect(decoded).toBeDefined();
    expect(decoded?.toolName).toBe('web&search');
    expect(decoded?.message).toBe('Need <b>token</b>');
    expect(decoded?.fields[0].label).toBe('API & Key');
    expect(decoded?.fields[0].description).toBe('Paste <token>');
    expect(decoded?.fields[0].defaultValue).toBe('A&B');
    expect(decoded?.fields[0].placeholder).toBe('https://api.example.com?x=1&y=2');
    expect(decoded?.fields[0].pattern).toBe('A&B');
    expect(decoded?.context.requested_variables).toEqual(['API & Key']);
  });
});
