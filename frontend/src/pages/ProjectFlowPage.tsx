import { useEffect, useMemo, useState } from "react";
import { useWatch, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Check, CheckCircle2, FileText, Info, LoaderCircle, Save, ShieldCheck, Trash2, UploadCloud, MessageCircleQuestion } from "lucide-react";
import { Link, useMatch, useNavigate, useParams } from "react-router-dom";
import { LongField, SelectField, TextField, ChoiceField } from "@/components/fields";
import { NavButtons, PageFrame, StepProgress, wizardSteps } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { projectSchema } from "@/lib/validation";
import { formatBytes } from "@/lib/utils";
import { api, type InterviewState } from "@/services/api";
import { emptyProject, type ProjectForm } from "@/types/project";

const stepFields: (keyof ProjectForm)[][] = [
  ["projectName", "description", "domain", "organizationType", "teamSize", "stakeholders"],
  [],
  ["requirementStability", "expectedChanges"],
  ["riskLevel", "securityCriticality", "complianceCriticality", "formalVerification", "failureImpact", "testingRequirement"],
  ["continuousDelivery", "legacyIntegration", "stakeholderAvailability", "complexity", "projectSize", "budgetConstraint", "timelineConstraint"],
  [], [],
];

const stepCopy = [
  { title: "Project idea", intro: "Tell us what you want to build. We will use this to tailor the discovery interview." },
  { title: "Adaptive discovery interview", intro: "Answer one focused question at a time. Follow-up questions adapt to what you tell us." },
  { title: "Requirements & change", intro: "Tell us how clear the requirements are today and how they may evolve." },
  { title: "Risk & assurance", intro: "Help us understand what must be protected, verified, and proven." },
  { title: "Delivery context", intro: "Share the practical conditions that shape the delivery approach." },
  { title: "Optional reference files", intro: "Add supporting material if it helps. You can continue without any files." },
  { title: "Review your project", intro: "Check your answers before sending the project brief." },
];

type AttachedFile = { file?: File; name: string; size: number; type: string; uploaded?: boolean };

function SummaryLine({ label, value }: { label: string; value: string | number }) {
  return <div className="flex flex-col gap-1 border-b border-slate-100 py-3 last:border-0 sm:flex-row sm:items-start sm:justify-between sm:gap-8"><span className="text-sm text-slate-500">{label}</span><span className="max-w-xl text-sm font-medium text-slate-800 sm:text-right">{value || "Not provided"}</span></div>;
}

export default function ProjectFlowPage() {
  const { projectId = "new" } = useParams();
  const navigate = useNavigate();
  const isNew = projectId === "new";
  const isQuestionnaireRoute = Boolean(useMatch("/projects/:projectId/questionnaire"));
  const [backendProjectId, setBackendProjectId] = useState<string | null>(isNew ? null : projectId);
  const [step, setStep] = useState(0);
  const [hydrating, setHydrating] = useState(!isNew);
  const [attached, setAttached] = useState<AttachedFile[]>([]);
  const [saving, setSaving] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [submissionMessage, setSubmissionMessage] = useState("");
  const [businessObjective, setBusinessObjective] = useState("");
  const [usersRoles, setUsersRoles] = useState("");
  const [interview, setInterview] = useState<InterviewState | null>(null);
  const [interviewIndex, setInterviewIndex] = useState(0);
  const [answerDraft, setAnswerDraft] = useState("");
  const [interviewBusy, setInterviewBusy] = useState(false);

  const { register, control, watch, trigger, getValues, reset, setValue, formState: { errors, isDirty } } = useForm<ProjectForm>({
    resolver: zodResolver(projectSchema),
    mode: "onTouched",
    defaultValues: emptyProject,
  });
  const values = useWatch({ control });

  useEffect(() => {
    let active = true;
    if (isNew) {
      setBackendProjectId(null);
      setSubmitted(false);
      setHydrating(false);
      setLoadError("");
      reset(emptyProject);
      setAttached([]);
      setInterview(null);
      setBusinessObjective("");
      setUsersRoles("");
      return;
    }
    setHydrating(true);
    setLoadError("");
    api.getProject(projectId).then((project) => {
      if (!active) return;
      const answers = project.questionnaire;
      reset({
        ...emptyProject,
        projectName: project.project_name,
        description: project.description,
        domain: project.domain,
        organizationType: project.organization_type,
        teamSize: project.team_size,
        stakeholders: project.stakeholders,
        initialRequirements: project.initial_requirements || "",
        ...(answers ? {
          requirementStability: answers.requirement_stability,
          riskLevel: answers.risk_level,
          securityCriticality: answers.security_criticality,
          complianceCriticality: answers.compliance_criticality,
          expectedChanges: answers.expected_changes,
          continuousDelivery: answers.continuous_delivery,
          legacyIntegration: answers.legacy_integration,
          formalVerification: answers.formal_verification,
          stakeholderAvailability: answers.stakeholder_availability,
          complexity: answers.complexity,
          projectSize: answers.project_size,
          failureImpact: answers.failure_impact,
          testingRequirement: answers.testing_requirement,
          budgetConstraint: answers.budget_constraint,
          timelineConstraint: answers.timeline_constraint,
        } : {}),
      });
      setBackendProjectId(project.id);
      setAttached((project.documents || []).map((document) => ({
        name: document.original_filename,
        size: document.size_bytes,
        type: document.content_type,
        uploaded: true,
      })));
      setSubmitted(Boolean(answers) && !isQuestionnaireRoute);
      setBusinessObjective(project.initial_requirements || project.description);
      setUsersRoles(project.stakeholders);
      setStep(answers ? 6 : 0);
      api.getInterviewState(project.id).then((state) => {
        if (!active) return;
        setInterview(state);
        setInterviewIndex(Math.max(0, state.asked_questions.length - 1));
        if (isQuestionnaireRoute && !answers) setStep(state.status === "completed" ? 2 : 1);
      }).catch(() => { /* Existing projects may predate adaptive interviews. */ });
    }).catch((error: unknown) => {
      if (active) setLoadError(error instanceof Error ? error.message : "Could not load project from the backend.");
    }).finally(() => active && setHydrating(false));
    return () => { active = false; };
  }, [projectId, isNew, isQuestionnaireRoute, reset]);

  async function next() {
    const fields = stepFields[step];
    if (fields.length && !(await trigger(fields))) return;
    if (step === 0) {
      setInterviewBusy(true);
      setSubmitError("");
      try {
        const formValues = getValues();
        let id = backendProjectId;
        if (!id) {
          setSubmissionMessage("Saving project profile…");
          const created = await api.createProject({ ...formValues, initialRequirements: businessObjective || formValues.initialRequirements, stakeholders: usersRoles || formValues.stakeholders });
          id = created.id;
          setBackendProjectId(id);
        } else {
          await api.updateProject(id, { ...formValues, initialRequirements: businessObjective || formValues.initialRequirements, stakeholders: usersRoles || formValues.stakeholders });
        }
        setSubmissionMessage("Preparing your tailored interview…");
        const state = await api.startInterview(id, {
          project_idea: formValues.description,
          business_objective: businessObjective.trim() || formValues.description,
          users_roles: usersRoles.trim() || formValues.stakeholders,
        });
        setInterview(state);
        setInterviewIndex(0);
        setStep(1);
        if (isNew) navigate(`/projects/${id}/questionnaire`, { replace: true });
      } catch (error: unknown) {
        setSubmitError(error instanceof Error ? error.message : "Could not start the interview.");
      } finally {
        setInterviewBusy(false);
        setSubmissionMessage("");
      }
      return;
    }
    if (step < wizardSteps.length - 1) setStep((current) => current + 1);
  }

  async function submitInterviewAnswer(skipped = false) {
    const question = interview?.asked_questions[interviewIndex];
    if (!question || !backendProjectId || (!skipped && !answerDraft.trim())) return;
    setInterviewBusy(true);
    setSubmitError("");
    try {
      const state = await api.answerInterview(backendProjectId, question.id, skipped ? "" : answerDraft.trim(), skipped);
      setInterview(state);
      if (state.current_question) setInterviewIndex(state.asked_questions.length - 1);
      else setInterviewIndex(Math.max(0, state.asked_questions.length - 1));
      setAnswerDraft("");
    } catch (error: unknown) {
      setSubmitError(error instanceof Error ? error.message : skipped ? "Could not skip this interview question." : "Could not save your interview answer.");
    } finally { setInterviewBusy(false); }
  }

  function saveInterviewAnswer() { return submitInterviewAnswer(false); }
  function skipInterviewQuestion() { return submitInterviewAnswer(true); }

  async function finishInterview() {
    if (!backendProjectId) return;
    setInterviewBusy(true);
    setSubmitError("");
    try {
      const state = await api.completeInterview(backendProjectId);
      setInterview(state);
      setStep(2);
    } catch (error: unknown) {
      setSubmitError(error instanceof Error ? error.message : "Could not complete the interview.");
    } finally { setInterviewBusy(false); }
  }

  useEffect(() => {
    const question = interview?.asked_questions[interviewIndex];
    const answer = question && interview ? interview.answers.find((item) => item.question_id === question.id)?.answer : "";
    setAnswerDraft(answer || "");
  }, [interview, interviewIndex]);

  function addFiles(fileList: FileList | null) {
    if (!fileList) return;
    const allowed = /\.(pdf|docx|txt)$/i;
    const incoming = Array.from(fileList);
    const invalid = incoming.filter((file) => !allowed.test(file.name));
    if (invalid.length) {
      setSubmitError(`Unsupported file type: ${invalid.map((file) => file.name).join(", ")}. Use PDF, DOCX, or TXT.`);
      return;
    }
    const oversized = incoming.filter((file) => file.size > 20 * 1024 * 1024);
    if (oversized.length) {
      setSubmitError(`These files exceed the 20 MB limit: ${oversized.map((file) => file.name).join(", ")}.`);
      return;
    }
    setSubmitError("");
    setAttached((current) => [...current, ...incoming.map((file) => ({ file, name: file.name, size: file.size, type: file.type }))]);
  }

  async function submit() {
    const valid = await trigger();
    if (!valid) { setStep(0); return; }
    setSaving(true);
    setSubmitError("");
    setSubmissionMessage("Preparing project submission…");
    try {
      const formValues = getValues();
      let savedProjectId = backendProjectId;
      if (savedProjectId) {
        setSubmissionMessage("Updating project in PostgreSQL…");
        await api.updateProject(savedProjectId, formValues);
      } else {
        setSubmissionMessage("Creating project in PostgreSQL…");
        const created = await api.createProject(formValues);
        savedProjectId = created.id;
        setBackendProjectId(savedProjectId);
      }

      setSubmissionMessage("Saving questionnaire answers…");
      await api.saveQuestionnaire(savedProjectId, formValues);

      for (const item of attached.filter((file) => file.file && !file.uploaded)) {
        setSubmissionMessage(`Uploading ${item.name}…`);
        await api.uploadDocument(savedProjectId, item.file as File);
        setAttached((current) => current.map((file) => file === item ? { ...file, file: undefined, uploaded: true } : file));
      }

      setSubmissionMessage("Loading the saved project from the backend…");
      navigate(`/projects/${savedProjectId}`, { replace: true });
    } catch (error: unknown) {
      setSubmitError(error instanceof Error ? error.message : "Project submission failed. Please try again.");
    } finally {
      setSaving(false);
      setSubmissionMessage("");
    }
  }

  const projectName = values.projectName || "New project";
  const fileNames = useMemo(() => attached.map((item) => item.name), [attached]);

  if (hydrating) return <PageFrame projectId={!isNew ? projectId : undefined}><div role="status" className="flex min-h-[50vh] items-center justify-center gap-3 text-slate-500"><LoaderCircle className="animate-spin" size={18} />Loading project from the backend…</div></PageFrame>;

  if (loadError) return <PageFrame projectId={!isNew ? projectId : undefined}><Card className="mx-auto mt-10 max-w-xl"><CardContent className="p-8"><h1 className="text-xl font-bold text-slate-900">Could not load project</h1><p role="alert" className="mt-3 text-sm text-rose-700">{loadError}</p><Button className="mt-6" variant="outline" onClick={() => navigate("/")}><ArrowLeft size={16} />Back to projects</Button></CardContent></Card></PageFrame>;

  if (submitted && !isQuestionnaireRoute) return <PageFrame projectId={!isNew ? projectId : undefined}>
    <Card className="mx-auto mt-10 max-w-2xl text-center"><CardContent className="px-8 py-12">
      <span className="mx-auto grid size-16 place-items-center rounded-2xl bg-emerald-50 text-emerald-600"><CheckCircle2 size={32} /></span>
      <h1 className="mt-5 text-3xl font-bold text-slate-950">Project brief submitted</h1>
      <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-500">“{projectName}” and its questionnaire are saved in PostgreSQL.</p>
      <p className="mt-3 text-xs text-slate-500">Backend project ID</p><code className="mt-1 inline-block rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-700">{backendProjectId}</code>
      <div className="mt-7 flex justify-center gap-3"><Button variant="outline" onClick={() => navigate("/")}><ArrowLeft size={16} />Home</Button><Button onClick={() => { setSubmitted(false); setStep(5); }}>Review brief</Button></div>
    </CardContent></Card>
  </PageFrame>;

  return <PageFrame projectId={!isNew ? projectId : undefined}>
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div><Link to="/" className="mb-3 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 no-underline hover:text-blue-700"><ArrowLeft size={13} />All projects</Link>
          <h1 className="text-2xl font-bold tracking-tight text-slate-950 md:text-3xl">{projectName}</h1><p className="mt-1 text-sm text-slate-500">A focused discovery interview for your project team.</p></div>
        <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500" aria-live="polite">{saving ? <LoaderCircle size={14} className="animate-spin" /> : isDirty ? <Save size={14} /> : <Check size={14} className="text-emerald-600" />}{saving ? submissionMessage || "Submitting to backend…" : isDirty ? "Changes not submitted" : backendProjectId ? "Loaded from backend" : "Ready to submit"}</div>
      </div>
      <StepProgress active={step} />
      <Card>
        <CardHeader className="border-b border-slate-100 px-6 pb-5 md:px-8">
          <div className="flex items-start justify-between gap-4"><div><Badge className="mb-3">{wizardSteps[step].title}</Badge><CardTitle className="text-2xl">{stepCopy[step].title}</CardTitle><CardDescription className="mt-2">{stepCopy[step].intro}</CardDescription></div><span className="hidden size-12 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-700 sm:grid">{(() => { const Icon = wizardSteps[step].icon; return <Icon size={21} />; })()}</span></div>
        </CardHeader>
        <CardContent className="px-6 py-6 md:px-8 md:py-8">
          {step === 0 && <div className="space-y-6">
            <div className="grid gap-5 md:grid-cols-2">
              <TextField name="projectName" label="Project name" placeholder="e.g. Digital lending transformation" register={register} error={errors.projectName?.message} />
              <LongField name="description" label="What do you want to build?" hint="Start with the project idea. Mention the problem and intended outcome; the system detects a likely domain." placeholder="e.g. An online service that helps patients find and book appointments…" register={register} error={errors.description?.message} />
              <SelectField name="domain" label="Domain hint (we will detect from your idea)" options={["Generic software system", "Banking", "Payments", "Lending", "Insurance", "Healthcare", "Education", "E-commerce", "Logistics", "Food delivery", "Government/public services", "HR/recruitment", "Manufacturing"]} register={register} error={errors.domain?.message} />
              <SelectField name="organizationType" label="Organization type" options={["Business", "Government", "Non-profit", "Healthcare provider", "Educational institution", "Startup", "Other"]} register={register} error={errors.organizationType?.message} />
              <TextField name="teamSize" label="Estimated team size" type="number" placeholder="8" register={register} error={errors.teamSize?.message} />
            </div>
            <label className="block space-y-2"><span className="text-sm font-medium text-slate-700">What business or user outcome should it achieve?</span><Textarea value={businessObjective} onChange={(event) => setBusinessObjective(event.target.value)} placeholder="e.g. Reduce appointment booking time and avoid scheduling conflicts" rows={3} /></label>
            <label className="block space-y-2"><span className="text-sm font-medium text-slate-700">Who will use or be affected by it?</span><Textarea value={usersRoles || values.stakeholders} onChange={(event) => { setUsersRoles(event.target.value); setValue("stakeholders", event.target.value, { shouldDirty: true, shouldValidate: true }); }} placeholder="e.g. patients, reception staff, clinicians" rows={3} /></label>
            <LongField name="stakeholders" label="Stakeholders and roles (for project record)" hint="Use the same roles above or add owners, operations, security, or compliance participants." placeholder="e.g. patients, reception staff, product owner" register={register} error={errors.stakeholders?.message} rows={2} />
            <LongField name="initialRequirements" label="Initial requirement notes (optional)" placeholder="Any early needs or stakeholder requests. Rough notes are fine." register={register} rows={2} />
          </div>}

          {step === 1 && <div className="space-y-6">
            {!interview ? <div role="status" className="flex items-center gap-3 rounded-xl bg-blue-50 p-5 text-sm text-blue-800"><LoaderCircle size={18} className="animate-spin" />Starting your project interview…</div> : <>
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-blue-50 p-4"><div><p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Detected domain</p><p className="mt-1 text-lg font-bold text-blue-950">{interview.detected_domain}</p></div><Badge>Question {interview.question_number} of {interview.maximum_questions}</Badge></div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${Math.round((interview.question_number / interview.maximum_questions) * 100)}%` }} /></div>
              {interview.current_question ? <>
                <div className="rounded-2xl border border-slate-200 bg-white p-5 md:p-7"><div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-blue-700"><MessageCircleQuestion size={16} />{interview.asked_questions[interviewIndex]?.topic.replaceAll("_", " ")}</div><h3 className="text-lg font-semibold leading-7 text-slate-950">{interview.asked_questions[interviewIndex]?.prompt}</h3><p className="mt-2 text-sm text-slate-500">{interview.asked_questions[interviewIndex]?.explanation}</p><label className="mt-5 block space-y-2"><span className="text-sm font-medium text-slate-700">Your answer</span><Textarea value={answerDraft} onChange={(event) => setAnswerDraft(event.target.value)} placeholder="Share what you know. You can say what is still undecided." rows={5} /></label></div>
                <div className="flex flex-wrap items-center justify-between gap-3"><Button type="button" variant="outline" onClick={() => setInterviewIndex((index) => Math.max(0, index - 1))} disabled={interviewIndex === 0 || interviewBusy}>Previous question</Button>{interviewIndex < interview.asked_questions.length - 1 && <Button type="button" variant="outline" onClick={() => setInterviewIndex((index) => Math.min(interview!.asked_questions.length - 1, index + 1))}>Next question</Button>}<div className="flex flex-wrap items-center gap-2"><Button type="button" variant="outline" onClick={skipInterviewQuestion} disabled={interviewBusy}>Skip question</Button><Button type="button" onClick={saveInterviewAnswer} disabled={!answerDraft.trim() || interviewBusy}>{interviewBusy ? <><LoaderCircle className="animate-spin" size={16} />Saving…</> : interviewIndex === interview.asked_questions.length - 1 ? "Save & continue" : "Save answer"}</Button></div></div>
              </> : <div className="space-y-5"><div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">Interview questions are complete. Review your answers and finish when you are ready.</div><section className="space-y-3"><h3 className="font-semibold text-slate-900">Project context</h3><SummaryLine label="Detected domain" value={interview.detected_domain} /><SummaryLine label="Business objective" value={interview.business_objective} /><SummaryLine label="Users and roles" value={interview.users_roles} /></section><section className="space-y-3"><h3 className="font-semibold text-slate-900">Interview answers</h3>{interview.asked_questions.map((question, index) => { const answer = interview.answers.find((item) => item.question_id === question.id); return <div key={question.id} className="rounded-xl border border-slate-200 p-4"><p className="text-sm font-semibold text-slate-800">{index + 1}. {question.prompt}</p><p className="mt-2 whitespace-pre-wrap text-sm text-slate-600">{answer?.skipped ? "Skipped" : answer?.answer || "Not answered"}</p></div>; })}</section><section className="space-y-2"><h3 className="font-semibold text-slate-900">Topics still to clarify</h3><p className="text-sm text-slate-500">These topics were not covered in enough detail during this interview.</p><div className="flex flex-wrap gap-2">{interview.uncovered_topics.map((topic) => <Badge key={topic} className="bg-amber-50 text-amber-800">{topic.replaceAll("_", " ")}</Badge>)}</div></section><Button type="button" onClick={finishInterview} disabled={interviewBusy || interview.status === "completed"}>{interviewBusy && <LoaderCircle className="animate-spin" size={16} />}{interview.status === "completed" ? "Interview completed" : "Finish interview & continue"}</Button></div>}
            </>}
          </div>}

          {step === 2 && <div className="space-y-7">
            <ChoiceField control={control} errors={errors} name="requirementStability" label="How stable are the requirements?" options={["Stable", "Moderately Changing", "Frequently Changing"]} />
            <ChoiceField control={control} errors={errors} name="expectedChanges" label="How often do you expect requirements to change?" options={["Rare", "Occasional", "Frequent"]} />
            <div className="rounded-xl bg-blue-50/70 p-4 text-sm leading-6 text-blue-900"><Info size={16} className="mr-2 inline" />If the goals are clear but details may evolve, say so. The delivery recommendation considers both stability and expected change.</div>
          </div>}

          {step === 3 && <div className="space-y-7">
            <div className="grid gap-7 md:grid-cols-2">
              <ChoiceField control={control} errors={errors} name="riskLevel" label="Overall project risk" options={["Low", "Medium", "High"]} />
              <ChoiceField control={control} errors={errors} name="securityCriticality" label="Security criticality" options={["Low", "Medium", "High"]} />
              <ChoiceField control={control} errors={errors} name="complianceCriticality" label="Compliance criticality" options={["Low", "Medium", "High"]} />
              <ChoiceField control={control} errors={errors} name="failureImpact" label="Impact if the system fails" options={["Low", "Medium", "High"]} />
            </div>
            <div className="grid gap-7 md:grid-cols-2">
              <ChoiceField control={control} errors={errors} name="formalVerification" label="Need formal verification?" options={["Yes", "No"]} />
              <ChoiceField control={control} errors={errors} name="testingRequirement" label="Expected testing rigor" options={["Basic", "Moderate", "Extensive"]} />
            </div>
          </div>}

          {step === 4 && <div className="space-y-7">
            <div className="grid gap-7 md:grid-cols-2">
              <ChoiceField control={control} errors={errors} name="continuousDelivery" label="Need continuous delivery?" options={["Yes", "No"]} />
              <ChoiceField control={control} errors={errors} name="legacyIntegration" label="Integrate with legacy systems?" options={["Yes", "No"]} />
              <ChoiceField control={control} errors={errors} name="stakeholderAvailability" label="Stakeholder availability" options={["Low", "Medium", "High"]} />
              <ChoiceField control={control} errors={errors} name="complexity" label="Project complexity" options={["Low", "Medium", "High"]} />
              <ChoiceField control={control} errors={errors} name="projectSize" label="Project size" options={["Small", "Medium", "Large"]} />
              <ChoiceField control={control} errors={errors} name="budgetConstraint" label="Budget constraint" options={["Low", "Medium", "High"]} />
              <ChoiceField control={control} errors={errors} name="timelineConstraint" label="Timeline constraint" options={["Flexible", "Moderate", "Strict"]} />
            </div>
          </div>}

          {step === 5 && <div className="space-y-5">
            <label htmlFor="project-files" className="flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/70 px-5 text-center transition hover:border-blue-300 hover:bg-blue-50/40">
              <span className="grid size-12 place-items-center rounded-2xl bg-white text-blue-700 shadow-sm"><UploadCloud size={22} /></span>
              <span className="mt-4 text-sm font-semibold text-slate-800">Choose reference files</span>
              <span className="mt-1 text-xs text-slate-500">PDF, DOCX, or TXT · multiple files allowed</span>
              <Input id="project-files" type="file" accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document" multiple className="sr-only" onChange={(event) => { addFiles(event.target.files); event.currentTarget.value = ""; }} />
            </label>
            <div className="flex gap-3 rounded-xl border border-blue-100 bg-blue-50/60 p-4 text-sm leading-6 text-blue-900"><Info size={17} className="mt-0.5 shrink-0" /><p>File upload is optional. Selected PDF, DOCX, and TXT documents are uploaded to the backend when you submit the project. Each file must be 20 MB or smaller.</p></div>
            {attached.length > 0 && <div className="space-y-2"><p className="text-sm font-semibold text-slate-700">Project documents ({attached.length})</p>{attached.map((item, index) => <div key={`${item.name}-${index}`} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3"><FileText size={17} className="shrink-0 text-blue-600" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-slate-800">{item.name}</p><p className="text-xs text-slate-400">{formatBytes(item.size)}{item.uploaded ? " · stored with this project" : " · uploads on submission"}</p></div>{!item.uploaded && <button type="button" aria-label={`Remove ${item.name}`} onClick={() => setAttached((files) => files.filter((_, i) => i !== index))} className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 size={15} /></button>}</div>)}</div>}
            {fileNames.length === 0 && <p className="text-center text-xs text-slate-400">No files selected. Continue to review your questionnaire.</p>}
          </div>}

          {step === 6 && <div className="space-y-6">
            <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4"><div className="flex items-center gap-2 text-sm font-semibold text-blue-900"><ShieldCheck size={17} />Review before submission</div><p className="mt-1 text-xs leading-5 text-blue-800">Your answers become a project brief for the next analysis phase. Recommendations and regulatory interpretations will still require human review.</p></div>
            <section><h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400">Project profile</h3><SummaryLine label="Project name" value={watch("projectName")} /><SummaryLine label="Domain" value={watch("domain")} /><SummaryLine label="Organization" value={watch("organizationType")} /><SummaryLine label="Team size" value={`${watch("teamSize")} people`} /><SummaryLine label="Description" value={watch("description")} /><SummaryLine label="Stakeholders" value={watch("stakeholders")} /></section>
            <section><h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400">Requirements & change</h3><SummaryLine label="Requirement stability" value={watch("requirementStability")} /><SummaryLine label="Expected changes" value={watch("expectedChanges")} /><SummaryLine label="Initial requirement notes" value={watch("initialRequirements") || "Not provided"} /></section>
            <section><h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400">Risk & assurance</h3><SummaryLine label="Project risk" value={watch("riskLevel")} /><SummaryLine label="Security / compliance" value={`${watch("securityCriticality")} / ${watch("complianceCriticality")} criticality`} /><SummaryLine label="Failure impact" value={watch("failureImpact")} /><SummaryLine label="Verification / testing" value={`${watch("formalVerification")} / ${watch("testingRequirement")}`} /></section>
            <section><h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400">Delivery context</h3><SummaryLine label="Continuous delivery" value={watch("continuousDelivery")} /><SummaryLine label="Legacy integration" value={watch("legacyIntegration")} /><SummaryLine label="Stakeholder availability" value={watch("stakeholderAvailability")} /><SummaryLine label="Complexity / size" value={`${watch("complexity")} / ${watch("projectSize")}`} /><SummaryLine label="Budget / timeline" value={`${watch("budgetConstraint")} / ${watch("timelineConstraint")}`} /></section>
            <section><h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-400">Reference files</h3><SummaryLine label="Selected files" value={fileNames.length ? fileNames.join(", ") : "None — optional"} /></section>
          </div>}

          {submitError && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{submitError}</div>}
          {step !== 1 && <NavButtons onBack={() => setStep((current) => Math.max(0, current - 1))} onNext={step === 6 ? submit : next} backDisabled={step === 0 || saving || interviewBusy} nextDisabled={saving || interviewBusy} nextLabel={step === 6 ? (saving ? "Submitting…" : "Submit project brief") : step === 5 ? "Review answers" : "Continue"} />}
        </CardContent>
      </Card>
      <p className="mt-4 flex items-center justify-center gap-2 text-center text-xs text-slate-400"><Save size={13} />Submit the project to save your answers to the backend. Saved projects load from the database when you return.</p>
    </div>
  </PageFrame>;
}

