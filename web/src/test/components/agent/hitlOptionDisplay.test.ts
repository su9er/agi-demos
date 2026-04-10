import { describe, expect, it } from 'vitest';

import {
  getOptionDescriptionText,
  getOptionLabelText,
  getOptionRiskList,
} from '@/utils/hitlOptionDisplay';

describe('getOptionLabelText', () => {
  it('decodes HTML entities and trims labels', () => {
    expect(getOptionLabelText('  A&amp;B  ')).toBe('A&B');
    expect(getOptionLabelText('&lt;b&gt;Deploy&lt;/b&gt;')).toBe('<b>Deploy</b>');
  });

  it('returns undefined for non-string values', () => {
    expect(getOptionLabelText(0)).toBeUndefined();
    expect(getOptionLabelText(null)).toBeUndefined();
  });
});

describe('getOptionDescriptionText', () => {
  it('returns undefined for non-string values like numeric zero', () => {
    expect(getOptionDescriptionText(0)).toBeUndefined();
    expect(getOptionDescriptionText(false)).toBeUndefined();
    expect(getOptionDescriptionText(null)).toBeUndefined();
  });

  it('returns undefined for blank strings', () => {
    expect(getOptionDescriptionText('')).toBeUndefined();
    expect(getOptionDescriptionText('   ')).toBeUndefined();
  });

  it('returns trimmed text for non-empty strings', () => {
    expect(getOptionDescriptionText('  option &amp; details  ')).toBe('option & details');
    expect(getOptionDescriptionText('0')).toBe('0');
  });
});

describe('getOptionRiskList', () => {
  it('returns only non-empty string risks', () => {
    expect(getOptionRiskList([' data &amp; loss ', 0, '', null, 'slowdown'])).toEqual([
      'data & loss',
      'slowdown',
    ]);
  });

  it('decodes HTML entities in risk text', () => {
    expect(getOptionRiskList(['&lt;b&gt;risk&lt;/b&gt;'])).toEqual(['<b>risk</b>']);
  });

  it('returns an empty list for non-array values', () => {
    expect(getOptionRiskList('data loss')).toEqual([]);
    expect(getOptionRiskList(null)).toEqual([]);
  });
});
