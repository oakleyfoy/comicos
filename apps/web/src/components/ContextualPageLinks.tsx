import { Link } from "react-router-dom";

export type ContextualPageLink = {
  label: string;
  to: string;
};

export function ContextualPageLinks({ links }: { links: ContextualPageLink[] }): JSX.Element | null {
  if (!links.length) {
    return null;
  }
  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
      {links.map((link) => (
        <Link key={`${link.to}-${link.label}`} className="font-medium text-patriot-blue hover:underline" to={link.to}>
          {link.label}
        </Link>
      ))}
    </div>
  );
}
