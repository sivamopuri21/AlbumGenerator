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
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200 ${
          isDragActive
            ? "border-primary-400 bg-primary-50/50 scale-[1.01]"
            : "border-gray-200 hover:border-primary-300 hover:bg-gray-50/50"
        }`}
      >
        <input {...getInputProps()} />
        <div className="text-gray-500">
          {isDragActive ? (
            <p className="text-primary-600 font-medium">Drop files here...</p>
          ) : (
            <>
              <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-2">
                <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
                </svg>
              </div>
              <p className="text-sm font-medium mb-0.5">Drag & drop files here, or click to browse</p>
              {hint && <p className="text-xs text-gray-400">{hint}</p>}
            </>
          )}
        </div>
      </div>
      {files.length > 0 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600 font-medium">
            {files.length} file{files.length !== 1 ? "s" : ""} selected
          </span>
          <button
            onClick={(e) => { e.stopPropagation(); onFiles([]); }}
            className="text-red-500 hover:text-red-600 text-xs font-medium"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
}
