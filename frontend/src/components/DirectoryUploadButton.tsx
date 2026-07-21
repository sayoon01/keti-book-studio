import {
  ChangeEvent,
  useRef,
} from "react";

interface DirectoryUploadButtonProps {
  disabled?: boolean;
  onDirectorySelected: (files: File[]) => void;
}

export function DirectoryUploadButton({
  disabled = false,
  onDirectorySelected,
}: DirectoryUploadButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const files = Array.from(
      event.target.files ?? [],
    );

    if (files.length > 0) {
      onDirectorySelected(files);
    }

    event.target.value = "";
  };

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        폴더 추가
      </button>

      <input
        ref={inputRef}
        type="file"
        multiple
        hidden
        onChange={handleChange}
        {...({
          webkitdirectory: "",
          directory: "",
        } as React.InputHTMLAttributes<HTMLInputElement>)}
      />
    </>
  );
}
