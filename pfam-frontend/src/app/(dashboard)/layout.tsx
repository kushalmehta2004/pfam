import { ReactNode } from "react";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white p-4">
        <p className="text-sm font-medium">PFAM Dashboard</p>
      </header>
      <div className="flex">
        <aside className="hidden w-64 border-r bg-white p-4 md:block">
          <nav className="space-y-2 text-sm">
            <p>Overview</p>
            <p>Campaigns</p>
            <p>Products</p>
            <p>Automation</p>
            <p>Settings</p>
          </nav>
        </aside>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}

