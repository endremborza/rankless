export type SurveySubmit = {
	role: string;
	customRole: string;
	scores: { id: string; score: number }[];
	customOption?: string;
	timestamp?: string;
};

export type SurveyRecord = {
	type: 'submit' | 'reject';
	payload: SurveySubmit | { reason?: string } | null;
	userId: string | null;
	timestamp: string;
};
