/**
 * Tests for timeline utility functions
 */

import { describe, it, expect } from 'vitest';

import {
  compareTimelineEvents,
  sortTimelineBySequence,
  isTimelineSorted,
  mergeTimelines,
} from '../../utils/timelineUtils';

import type { TimelineEvent } from '../../types/agent';

describe('timelineUtils', () => {
  describe('compareTimelineEvents', () => {
    it('should sort by eventTimeUs when both are valid', () => {
      const a: TimelineEvent = {
        id: 'a',
        type: 'user_message',
        eventTimeUs: 1000,
        eventCounter: 0,
        timestamp: 1,
        content: 'First',
        role: 'user',
      };
      const b: TimelineEvent = {
        id: 'b',
        type: 'user_message',
        eventTimeUs: 2000,
        eventCounter: 0,
        timestamp: 2,
        content: 'Second',
        role: 'user',
      };

      expect(compareTimelineEvents(a, b)).toBeLessThan(0);
      expect(compareTimelineEvents(b, a)).toBeGreaterThan(0);
      expect(compareTimelineEvents(a, a)).toBe(0);
    });

    it('should place null eventTimeUs at the end', () => {
      const withTime: TimelineEvent = {
        id: 'a',
        type: 'user_message',
        eventTimeUs: 1000,
        eventCounter: 0,
        timestamp: 1,
        content: 'With time',
        role: 'user',
      };
      const withoutTime: TimelineEvent = {
        id: 'b',
        type: 'thought',
        eventTimeUs: null as any,
        eventCounter: 0,
        timestamp: 0,
        content: 'Without time',
      };

      expect(compareTimelineEvents(withTime, withoutTime)).toBeLessThan(0);
      expect(compareTimelineEvents(withoutTime, withTime)).toBeGreaterThan(0);
    });

    it('should place undefined eventTimeUs at the end', () => {
      const withTime: TimelineEvent = {
        id: 'a',
        type: 'user_message',
        eventTimeUs: 1000,
        eventCounter: 0,
        timestamp: 1,
        content: 'With time',
        role: 'user',
      };
      const withoutTime: TimelineEvent = {
        id: 'b',
        type: 'thought',
        eventTimeUs: undefined as any,
        eventCounter: 0,
        timestamp: 0,
        content: 'Without time',
      };

      expect(compareTimelineEvents(withTime, withoutTime)).toBeLessThan(0);
      expect(compareTimelineEvents(withoutTime, withTime)).toBeGreaterThan(0);
    });

    it('should fall back to timestamp when both eventTimeUs are invalid', () => {
      const a: TimelineEvent = {
        id: 'a',
        type: 'thought',
        eventTimeUs: null as any,
        eventCounter: 0,
        timestamp: 1000,
        content: 'First by timestamp',
      };
      const b: TimelineEvent = {
        id: 'b',
        type: 'thought',
        eventTimeUs: undefined as any,
        eventCounter: 0,
        timestamp: 2000,
        content: 'Second by timestamp',
      };

      expect(compareTimelineEvents(a, b)).toBeLessThan(0);
      expect(compareTimelineEvents(b, a)).toBeGreaterThan(0);
    });

    it('should fall back to id when both eventTimeUs and timestamps are equal', () => {
      const a: TimelineEvent = {
        id: 'a',
        type: 'thought',
        eventTimeUs: null as any,
        eventCounter: 0,
        timestamp: 1000,
        content: 'A',
      };
      const b: TimelineEvent = {
        id: 'b',
        type: 'thought',
        eventTimeUs: null as any,
        eventCounter: 0,
        timestamp: 1000,
        content: 'B',
      };

      expect(compareTimelineEvents(a, b)).toBeLessThan(0);
      expect(compareTimelineEvents(b, a)).toBeGreaterThan(0);
    });

    it('should handle NaN eventTimeUs', () => {
      const withTime: TimelineEvent = {
        id: 'a',
        type: 'user_message',
        eventTimeUs: 1000,
        eventCounter: 0,
        timestamp: 1,
        content: 'With time',
        role: 'user',
      };
      const withNaN: TimelineEvent = {
        id: 'b',
        type: 'thought',
        eventTimeUs: NaN,
        eventCounter: 0,
        timestamp: 0,
        content: 'With NaN',
      };

      expect(compareTimelineEvents(withTime, withNaN)).toBeLessThan(0);
      expect(compareTimelineEvents(withNaN, withTime)).toBeGreaterThan(0);
    });

    it('should compare by eventCounter when eventTimeUs are equal', () => {
      const a: TimelineEvent = {
        id: 'a',
        type: 'user_message',
        eventTimeUs: 1000,
        eventCounter: 1,
        timestamp: 1,
        content: 'First',
        role: 'user',
      };
      const b: TimelineEvent = {
        id: 'b',
        type: 'user_message',
        eventTimeUs: 1000,
        eventCounter: 2,
        timestamp: 1,
        content: 'Second',
        role: 'user',
      };

      expect(compareTimelineEvents(a, b)).toBeLessThan(0);
      expect(compareTimelineEvents(b, a)).toBeGreaterThan(0);
    });
  });

  describe('sortTimelineBySequence', () => {
    it('should sort timeline by eventTimeUs in ascending order', () => {
      const timeline: TimelineEvent[] = [
        {
          id: 'c',
          type: 'thought',
          eventTimeUs: 3000,
          eventCounter: 0,
          timestamp: 3,
          content: 'Third',
        },
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'First',
          role: 'user',
        },
        {
          id: 'b',
          type: 'assistant_message',
          eventTimeUs: 2000,
          eventCounter: 0,
          timestamp: 2,
          content: 'Second',
          role: 'assistant',
        },
      ];

      const sorted = sortTimelineBySequence(timeline);

      expect(sorted[0].eventTimeUs).toBe(1000);
      expect(sorted[1].eventTimeUs).toBe(2000);
      expect(sorted[2].eventTimeUs).toBe(3000);
      expect(sorted[0].id).toBe('a');
      expect(sorted[1].id).toBe('b');
      expect(sorted[2].id).toBe('c');
    });

    it('should place events with null/undefined eventTimeUs at the end', () => {
      const timeline: TimelineEvent[] = [
        {
          id: 'null-time',
          type: 'thought',
          eventTimeUs: null as any,
          eventCounter: 0,
          timestamp: 500,
          content: 'Null eventTimeUs',
        },
        {
          id: 'valid-time',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'Valid eventTimeUs',
          role: 'user',
        },
        {
          id: 'undefined-time',
          type: 'thought',
          eventTimeUs: undefined as any,
          eventCounter: 0,
          timestamp: 600,
          content: 'Undefined eventTimeUs',
        },
      ];

      const sorted = sortTimelineBySequence(timeline);

      expect(sorted[0].id).toBe('valid-time');
      // The other two should be at the end, sorted by timestamp
      expect(sorted[1].id).toBe('null-time');
      expect(sorted[2].id).toBe('undefined-time');
    });

    it('should not mutate the original array', () => {
      const timeline: TimelineEvent[] = [
        {
          id: 'b',
          type: 'thought',
          eventTimeUs: 2000,
          eventCounter: 0,
          timestamp: 2,
          content: 'Second',
        },
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'First',
          role: 'user',
        },
      ];

      const sorted = sortTimelineBySequence(timeline);

      // Original should remain unchanged
      expect(timeline[0].id).toBe('b');
      expect(timeline[1].id).toBe('a');

      // Sorted should be in correct order
      expect(sorted[0].id).toBe('a');
      expect(sorted[1].id).toBe('b');
    });

    it('should handle empty array', () => {
      const sorted = sortTimelineBySequence([]);
      expect(sorted).toEqual([]);
    });

    it('should handle single element', () => {
      const timeline: TimelineEvent[] = [
        {
          id: 'only',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'Only',
          role: 'user',
        },
      ];

      const sorted = sortTimelineBySequence(timeline);
      expect(sorted).toHaveLength(1);
      expect(sorted[0].id).toBe('only');
    });
  });

  describe('isTimelineSorted', () => {
    it('should return true for sorted timeline', () => {
      const timeline: TimelineEvent[] = [
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'A',
          role: 'user',
        },
        {
          id: 'b',
          type: 'thought',
          eventTimeUs: 2000,
          eventCounter: 0,
          timestamp: 2,
          content: 'B',
        },
        {
          id: 'c',
          type: 'assistant_message',
          eventTimeUs: 3000,
          eventCounter: 0,
          timestamp: 3,
          content: 'C',
          role: 'assistant',
        },
      ];

      expect(isTimelineSorted(timeline)).toBe(true);
    });

    it('should return false for unsorted timeline', () => {
      const timeline: TimelineEvent[] = [
        {
          id: 'b',
          type: 'thought',
          eventTimeUs: 2000,
          eventCounter: 0,
          timestamp: 2,
          content: 'B',
        },
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'A',
          role: 'user',
        },
        {
          id: 'c',
          type: 'assistant_message',
          eventTimeUs: 3000,
          eventCounter: 0,
          timestamp: 3,
          content: 'C',
          role: 'assistant',
        },
      ];

      expect(isTimelineSorted(timeline)).toBe(false);
    });

    it('should skip invalid eventTimeUs during check', () => {
      const timeline: TimelineEvent[] = [
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'A',
          role: 'user',
        },
        {
          id: 'b',
          type: 'thought',
          eventTimeUs: null as any,
          eventCounter: 0,
          timestamp: 2,
          content: 'B',
        },
        {
          id: 'c',
          type: 'assistant_message',
          eventTimeUs: 3000,
          eventCounter: 0,
          timestamp: 3,
          content: 'C',
          role: 'assistant',
        },
      ];

      expect(isTimelineSorted(timeline)).toBe(true);
    });

    it('should return true for empty array', () => {
      expect(isTimelineSorted([])).toBe(true);
    });

    it('should return true for single element', () => {
      const timeline: TimelineEvent[] = [
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'A',
          role: 'user',
        },
      ];
      expect(isTimelineSorted(timeline)).toBe(true);
    });
  });

  describe('mergeTimelines', () => {
    it('should merge and sort two timelines', () => {
      const primary: TimelineEvent[] = [
        {
          id: 'b',
          type: 'thought',
          eventTimeUs: 2000,
          eventCounter: 0,
          timestamp: 2,
          content: 'B',
        },
      ];
      const secondary: TimelineEvent[] = [
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'A',
          role: 'user',
        },
      ];

      const merged = mergeTimelines(primary, secondary);

      expect(merged).toHaveLength(2);
      expect(merged[0].eventTimeUs).toBe(1000);
      expect(merged[1].eventTimeUs).toBe(2000);
    });

    it('should deduplicate events by id', () => {
      const primary: TimelineEvent[] = [
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'A',
          role: 'user',
        },
      ];
      const secondary: TimelineEvent[] = [
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'A',
          role: 'user',
        },
        {
          id: 'b',
          type: 'thought',
          eventTimeUs: 2000,
          eventCounter: 0,
          timestamp: 2,
          content: 'B',
        },
      ];

      const merged = mergeTimelines(primary, secondary);

      expect(merged).toHaveLength(2);
      expect(merged[0].id).toBe('a');
      expect(merged[1].id).toBe('b');
    });

    it('should prefer primary timeline for duplicates', () => {
      const primary: TimelineEvent[] = [
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'From Primary',
          role: 'user',
        },
      ];
      const secondary: TimelineEvent[] = [
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'From Secondary',
          role: 'user',
        },
      ];

      const merged = mergeTimelines(primary, secondary);

      expect(merged).toHaveLength(1);
      expect(merged[0].content).toBe('From Primary');
    });

    it('should handle empty primary', () => {
      const secondary: TimelineEvent[] = [
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'A',
          role: 'user',
        },
      ];

      const merged = mergeTimelines([], secondary);

      expect(merged).toHaveLength(1);
      expect(merged[0].id).toBe('a');
    });

    it('should handle empty secondary', () => {
      const primary: TimelineEvent[] = [
        {
          id: 'a',
          type: 'user_message',
          eventTimeUs: 1000,
          eventCounter: 0,
          timestamp: 1,
          content: 'A',
          role: 'user',
        },
      ];

      const merged = mergeTimelines(primary, []);

      expect(merged).toHaveLength(1);
      expect(merged[0].id).toBe('a');
    });
  });
});
