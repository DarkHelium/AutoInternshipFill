import { Welcome } from "../welcome/welcome";

export function meta() {
  return [
    { title: "New React Router App" },
    { name: "description", content: "Welcome to React Router!" },
  ];
}

export default function Home() {
  return (
    <div className="space-y-4">
      <Welcome />
      <div className="rounded-xl bg-white p-4">
        <p className="text-sm text-gray-600">
          Use the navigation above to browse jobs, edit your profile, or view run logs.
        </p>
      </div>
    </div>
  );
}
