export type CorrectionAction =
  | { kind: 'confirm'; speakerId: string; name: string }
  | { kind: 'existing'; speakerId: string; name: string }
  | { kind: 'new'; name: string }
  | { kind: 'unknown' }
  | { kind: 'ignore' };

export const buildSpeakerAssignments = (
  pendingCorrections: Map<string, CorrectionAction>,
  needsReviewMode: boolean,
): Record<string, string> => {
  const assignments: Record<string, string> = {};
  for (const [label, action] of pendingCorrections.entries()) {
    switch (action.kind) {
      case 'confirm':
      case 'existing':
        assignments[label] = action.speakerId;
        break;
      case 'new':
        assignments[label] = `new:${action.name}`;
        break;
      case 'unknown':
        assignments[label] = needsReviewMode ? 'ignore' : 'unknown';
        break;
      case 'ignore':
        assignments[label] = 'ignore';
        break;
    }
  }
  return assignments;
};
