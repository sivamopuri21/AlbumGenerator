"use client";
import { useCallback } from "react";
import { useDropzone, FileRejection } from "react-dropzone";

interface Props {
  label: string;
  accept: Record<string, string[]>;
  files: File[];
  onFiles: (files: File[]) => void;
  maxFiles?: number;
  hint?: string;
}

export default function Dropzone({ label, accept, files, onFiles, maxFiles, hint }: Props) {
  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      if (rejected.length) {
        alert(`Some files were rejected. Check file types and sizes.`);
      }
      onFiles([...files, ...accepted].slice(0, maxFiles || 1000));
    },
    [files, onFiles, maxFiles]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    maxFiles: maxFiles || 1000,
  });

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? "border-primary-500 bg-primary-500/5"
            : "border-gray-300 hover:border-gray-400"
        }`}
      >
        <input {...getInputProps()} />
        <div className="text-gray-500">
          {isDragActive ? (
            <p>Drop files here...</p>
          ) : (
            <>
              <p className="text-lg mb-1">Drag & drop files here, or click to browse</p>
              {hint && <p className="text-sm text-gray-400">{hint}</p>}
            </>
          )}
        </div>
      </div>
      {files.length > 0 && (
        <p className="text-sm text-gray-500">
          {files.length} file{files.length !== 1 ? "s" : ""} selected
          <button
            onClick={(e) => { e.stopPropagation(); onFiles([]); }}
            className="ml-2 text-red-500 hover:underline"
          >
            Clear
          </button>
        </p>
      )}
    </div>
  );
}
