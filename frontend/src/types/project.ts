export type ProjectForm = {
  projectName: string;
  description: string;
  domain: string;
  organizationType: string;
  teamSize: number;
  stakeholders: string;
  initialRequirements: string;
  requirementStability: string;
  riskLevel: string;
  securityCriticality: string;
  complianceCriticality: string;
  expectedChanges: string;
  continuousDelivery: string;
  legacyIntegration: string;
  formalVerification: string;
  stakeholderAvailability: string;
  complexity: string;
  projectSize: string;
  failureImpact: string;
  testingRequirement: string;
  budgetConstraint: string;
  timelineConstraint: string;
};

export const emptyProject: ProjectForm = {
  projectName: "", description: "", domain: "Generic software system", organizationType: "Other", teamSize: 8,
  stakeholders: "", initialRequirements: "", requirementStability: "",
  riskLevel: "", securityCriticality: "", complianceCriticality: "",
  expectedChanges: "", continuousDelivery: "", legacyIntegration: "",
  formalVerification: "", stakeholderAvailability: "", complexity: "",
  projectSize: "", failureImpact: "", testingRequirement: "",
  budgetConstraint: "", timelineConstraint: "",
};
