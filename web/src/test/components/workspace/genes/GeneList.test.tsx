import { describe, expect, it } from 'vitest';

import { GeneList } from '@/components/workspace/genes/GeneList';
import { render, screen } from '@/test/utils';

describe('GeneList', () => {
  it('marks gene list as a hosted non-authoritative projection', () => {
    render(<GeneList genes={[]} />);

    const boundaryBadge = screen.getByText('blackboard.genesSurfaceHint').closest('div');
    expect(boundaryBadge).toHaveAttribute('data-blackboard-boundary', 'hosted');
    expect(boundaryBadge).toHaveAttribute('data-blackboard-authority', 'non-authoritative');
  });
});
