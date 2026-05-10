"use client";

interface Props {
  progress: number;
  status: string;
  message: string;
}

const STATUS_LABELS: Record<string, string> = {
  pending: "Queued",
  uploading: "Uploading",
  preprocessing: "Preprocessing Images",
  deduplicating: "Removing Duplicates",
  filtering: "Quality Filtering",
  detecting_faces: "Detecting Faces",
  parsing_templates: "Parsing PSD Templates",
  assigning_photos: "Assigning Photos to Pages",
  rendering: "Rendering Pages",
  exporting: "Exporting (PDF + JPEG + PSD)",
  completed: "Complete",
  failed: "Failed",
};

export default function ProgressBar({ progress, status, message }: Props) {
  const label = STATUS_LABELS[status] || status;
  const failed = status === "failed";

  return (
    <div className="space-y-3">
      <div className="flex justify-between text-sm">
        <span className={`font-medium ${failed ? "text-red-600" : "text-gray-700"}`}>
          {label}
        </span>
        <span className="text-gray-500">{Math.round(progress)}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            failed ? "bg-red-500" : "bg-primary-600"
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>
      {message && <p className="text-sm text-gray-500">{message}</p>}
    </div>
  );
}
