export function Welcome() {
  return (
    <main className="flex items-center justify-center pt-12 pb-4">
      <div className="flex-1 flex flex-col items-center gap-6 min-h-0">
        <h2 className="text-2xl font-semibold">Auto-Apply Dashboard</h2>
        <div className="max-w-[560px] w-full space-y-4 px-4">
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <p className="text-gray-700 dark:text-gray-200">
              Use the navigation above to browse jobs, edit your profile, or view live runs.
            </p>
            <div className="mt-4 flex gap-3">
              <a href="/jobs" className="rounded-md bg-indigo-600 px-3 py-1.5 text-white">View Jobs</a>
              <a href="/profile" className="rounded-md bg-gray-900 px-3 py-1.5 text-white">Profile</a>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
