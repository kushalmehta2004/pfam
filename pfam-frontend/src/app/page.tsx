import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold">PFAM</h1>
      <p className="text-sm text-slate-600">Phase 0 foundation is running.</p>
      <div className="flex gap-3">
        <Link className="rounded border px-4 py-2 text-sm" href="/sign-in">
          Sign in
        </Link>
        <Link className="rounded border px-4 py-2 text-sm" href="/sign-up">
          Sign up
        </Link>
        <Link className="rounded border px-4 py-2 text-sm" href="/overview">
          Dashboard
        </Link>
      </div>
    </main>
  );
}

