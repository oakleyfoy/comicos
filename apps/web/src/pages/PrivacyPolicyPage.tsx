import { Link } from "react-router-dom";

export function PrivacyPolicyPage() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-4xl px-6 py-12 sm:px-8 lg:px-10">
        <div className="flex items-center justify-between gap-4">
          <Link to="/" className="text-sm font-semibold text-patriot-blue hover:text-patriot-red">
            ComicOS
          </Link>
          <Link to="/login" className="text-sm font-semibold text-patriot-blue hover:text-patriot-red">
            Sign in
          </Link>
        </div>

        <article className="mt-8 rounded-3xl border border-blue-200 bg-white p-6 shadow-lg shadow-blue-900/10 sm:p-8">
          <header className="space-y-3 border-b border-slate-200 pb-6">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Privacy Policy</p>
            <h1 className="text-3xl font-semibold tracking-tight text-patriot-navy sm:text-4xl">
              Privacy Policy for ComicOS Midtown Sync Helper
            </h1>
            <p className="text-sm text-slate-600">Last updated: June 10, 2026</p>
          </header>

          <section className="mt-6 space-y-4 text-sm leading-7 text-slate-700">
            <p>
              ComicOS Midtown Sync Helper is a browser extension that allows ComicOS users to import Midtown
              Comics order information into their ComicOS account.
            </p>
          </section>

          <section className="mt-8 space-y-3">
            <h2 className="text-xl font-semibold text-patriot-navy">Information We Collect</h2>
            <p className="text-sm leading-7 text-slate-700">
              When a user manually initiates a capture, the extension may collect information visible on the user&apos;s
              Midtown Comics order page, including:
            </p>
            <ul className="list-disc space-y-2 pl-5 text-sm leading-7 text-slate-700">
              <li>Order numbers</li>
              <li>Product titles</li>
              <li>Comic issue information</li>
              <li>Variant and cover information</li>
              <li>Cover image URLs</li>
              <li>Product URLs</li>
              <li>Item quantities</li>
              <li>Order dates</li>
              <li>Order totals</li>
              <li>Shipping status</li>
            </ul>
            <p className="text-sm leading-7 text-slate-700">
              The extension may also collect account-identifying information that appears on the order page,
              including:
            </p>
            <ul className="list-disc space-y-2 pl-5 text-sm leading-7 text-slate-700">
              <li>Email address</li>
              <li>Account name</li>
              <li>Shipping name and address</li>
            </ul>
          </section>

          <section className="mt-8 space-y-3">
            <h2 className="text-xl font-semibold text-patriot-navy">How Information Is Used</h2>
            <p className="text-sm leading-7 text-slate-700">
              Collected information is transmitted to the user&apos;s ComicOS account and is used solely for:
            </p>
            <ul className="list-disc space-y-2 pl-5 text-sm leading-7 text-slate-700">
              <li>Purchase imports</li>
              <li>Collection management</li>
              <li>Inventory tracking</li>
              <li>Receiving workflows</li>
              <li>Cover identification</li>
              <li>Order history management</li>
            </ul>
          </section>

          <section className="mt-8 space-y-3">
            <h2 className="text-xl font-semibold text-patriot-navy">Data Sharing</h2>
            <p className="text-sm leading-7 text-slate-700">ComicOS does not sell user data.</p>
            <p className="text-sm leading-7 text-slate-700">
              ComicOS does not share collected data with third parties except as necessary to operate ComicOS
              services for the user or as required by law.
            </p>
          </section>

          <section className="mt-8 space-y-3">
            <h2 className="text-xl font-semibold text-patriot-navy">Credentials</h2>
            <p className="text-sm leading-7 text-slate-700">
              The extension does not collect, store, or transmit Midtown Comics passwords, authentication
              credentials, MFA codes, or security answers.
            </p>
            <p className="text-sm leading-7 text-slate-700">
              Users authenticate directly with Midtown Comics through Midtown&apos;s own login system.
            </p>
          </section>

          <section className="mt-8 space-y-3">
            <h2 className="text-xl font-semibold text-patriot-navy">User Control</h2>
            <p className="text-sm leading-7 text-slate-700">
              The extension only captures information after a user explicitly initiates a capture action.
            </p>
            <p className="text-sm leading-7 text-slate-700">
              The extension does not continuously monitor browsing activity and only operates on supported Midtown
              Comics pages.
            </p>
          </section>

          <section className="mt-8 space-y-3">
            <h2 className="text-xl font-semibold text-patriot-navy">Data Retention</h2>
            <p className="text-sm leading-7 text-slate-700">
              Imported order information is retained within the user&apos;s ComicOS account until the user deletes the
              imported data or closes their account, subject to any backup and disaster recovery retention processes
              used by ComicOS.
            </p>
          </section>

          <section className="mt-8 space-y-3">
            <h2 className="text-xl font-semibold text-patriot-navy">Security</h2>
            <p className="text-sm leading-7 text-slate-700">
              ComicOS uses reasonable administrative, technical, and organizational safeguards designed to protect
              imported user data from unauthorized access, disclosure, alteration, or destruction.
            </p>
          </section>

          <section className="mt-8 space-y-3 border-t border-slate-200 pt-6">
            <h2 className="text-xl font-semibold text-patriot-navy">Contact</h2>
            <p className="text-sm leading-7 text-slate-700">
              If you have questions about this Privacy Policy, contact{" "}
              <a className="font-semibold text-patriot-blue hover:text-patriot-red" href="mailto:support@comicosapp.com">
                support@comicosapp.com
              </a>
            </p>
            <p className="text-sm leading-7 text-slate-700">
              Website:{" "}
              <a className="font-semibold text-patriot-blue hover:text-patriot-red" href="https://comicosapp.com">
                https://comicosapp.com
              </a>
            </p>
          </section>
        </article>
      </div>
    </main>
  );
}
