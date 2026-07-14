export function ComingSoon({ label }: { label: string }) {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center text-slate-400">
        <div className="text-base mb-1">{label} 화면은 아직 준비 중입니다.</div>
        <div className="text-sm">다음 단계에서 만들 예정입니다.</div>
      </div>
    </div>
  );
}
