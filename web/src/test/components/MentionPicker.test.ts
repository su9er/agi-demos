/**
 * extractMentionQuery tests — Track B P2-3 phase-2 (b-fe-mention).
 *
 * Agent First guardrail: the helper is purely structural (boundary +
 * whitespace detection). No NL classification.
 */

import { describe, it, expect } from 'vitest';

import { extractMentionQuery } from '@/components/agent/MentionPicker';

describe('extractMentionQuery', () => {
  it('returns null when there is no @', () => {
    expect(extractMentionQuery('hello world')).toBeNull();
  });

  it('extracts an empty query right after a leading @', () => {
    expect(extractMentionQuery('@')).toBe('');
  });

  it('extracts the characters typed after @', () => {
    expect(extractMentionQuery('hello @ali')).toBe('ali');
  });

  it('requires the @ to be at a word boundary', () => {
    expect(extractMentionQuery('foo@bar')).toBeNull();
  });

  it('closes the mention when whitespace appears after @', () => {
    expect(extractMentionQuery('@ali and then')).toBeNull();
  });

  it('returns the latest active mention when multiple @ exist', () => {
    expect(extractMentionQuery('@alpha said hi @be')).toBe('be');
  });
});
