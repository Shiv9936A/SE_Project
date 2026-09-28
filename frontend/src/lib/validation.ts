import { z } from "zod";

const choice = (options: [string, ...string[]]) => z.enum(options);
export const projectSchema = z.object({
  projectName: z.string().trim().min(2, "Enter a project name."),
  description: z.string().trim().min(12, "Add a little more context (at least 12 characters)."),
  domain: z.string().min(1, "Choose a financial domain."),
  organizationType: z.string().min(1, "Choose an organization type."),
  teamSize: z.number().int().min(1, "Team size must be at least 1.").max(10000, "Enter a realistic team size."),
  stakeholders: z.string().trim().min(2, "Add at least one stakeholder group."),
  initialRequirements: z.string().optional(),
  requirementStability: choice(["Stable", "Moderately Changing", "Frequently Changing"]),
  riskLevel: choice(["Low", "Medium", "High"]),
  securityCriticality: choice(["Low", "Medium", "High"]),
  complianceCriticality: choice(["Low", "Medium", "High"]),
  expectedChanges: choice(["Rare", "Occasional", "Frequent"]),
  continuousDelivery: choice(["Yes", "No"]),
  legacyIntegration: choice(["Yes", "No"]),
  formalVerification: choice(["Yes", "No"]),
  stakeholderAvailability: choice(["Low", "Medium", "High"]),
  complexity: choice(["Low", "Medium", "High"]),
  projectSize: choice(["Small", "Medium", "Large"]),
  failureImpact: choice(["Low", "Medium", "High"]),
  testingRequirement: choice(["Basic", "Moderate", "Extensive"]),
  budgetConstraint: choice(["Low", "Medium", "High"]),
  timelineConstraint: choice(["Flexible", "Moderate", "Strict"]),
});
