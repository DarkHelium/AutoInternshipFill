export type Job = {
  id: string;
  company: string;
  role: string;
  location?: string;
  applyUrl: string;
  datePosted?: string; // ISO
  ats?: "greenhouse" | "lever" | "workday" | "ashby" | "other";
  status: "new" | "queued" | "tailored" | "applied" | "skipped" | "error";
};

export type TailorResult = {
  jobId: string;
  keywords: string[];
  diffHtml?: string; // server-generated HTML diff for preview
  pdfUrl?: string; // tailored resume artifact
};

export type RunEvent =
  | { type: "log"; ts: string; level: "info" | "warn" | "error"; message: string }
  | { type: "screenshot"; ts: string; url: string }
  | { type: "gate"; ts: string; prompt: string } // human-in-the-loop
  | { type: "done"; ts: string; ok: boolean; receiptUrl?: string };

export type ApplicantProfile = {
  name: string; email: string; phone?: string;
  school?: string; gradDate?: string;
  workAuth?: { usCitizen?: boolean; sponsorship?: boolean };
  links?: { github?: string; portfolio?: string; linkedin?: string };
  skills?: string[];
  answers?: Record<string, string>;
};


