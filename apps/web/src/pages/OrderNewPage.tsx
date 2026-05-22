import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type OrderCreatePayload, type OrderItemPayload } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

interface OrderItemDraft {
  publisher: string;
  title: string;
  issueNumber: string;
  coverName: string;
  printing: string;
  ratio: string;
  variantType: string;
  coverArtist: string;
  quantity: string;
  rawItemPrice: string;
}

interface ItemFieldErrors {
  publisher?: string;
  title?: string;
  issueNumber?: string;
  quantity?: string;
  rawItemPrice?: string;
}

interface FormErrors {
  retailer?: string;
  orderDate?: string;
  shippingAmount?: string;
  taxAmount?: string;
  items: Record<number, ItemFieldErrors>;
}

const emptyItem = (): OrderItemDraft => ({
  publisher: "",
  title: "",
  issueNumber: "",
  coverName: "",
  printing: "",
  ratio: "",
  variantType: "",
  coverArtist: "",
  quantity: "1",
  rawItemPrice: "0.00",
});

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

function normalizeOptional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function emptyFormErrors(): FormErrors {
  return {
    items: {},
  };
}

export function OrderNewPage() {
  const [retailer, setRetailer] = useState("");
  const [orderDate, setOrderDate] = useState(new Date().toISOString().slice(0, 10));
  const [sourceType, setSourceType] = useState("manual");
  const [shippingAmount, setShippingAmount] = useState("0.00");
  const [taxAmount, setTaxAmount] = useState("0.00");
  const [items, setItems] = useState<OrderItemDraft[]>([emptyItem()]);
  const [error, setError] = useState<string | null>(null);
  const [formErrors, setFormErrors] = useState<FormErrors>(emptyFormErrors());
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState<{
    orderId: number;
    totalCopiesCreated: number;
    allInTotal: string;
  } | null>(null);

  const subtotal = useMemo(
    () =>
      items.reduce((sum, item) => {
        const quantity = Number(item.quantity || 0);
        const rawItemPrice = Number(item.rawItemPrice || 0);
        return sum + quantity * rawItemPrice;
      }, 0),
    [items],
  );

  const estimatedAllInTotal =
    subtotal + Number(shippingAmount || 0) + Number(taxAmount || 0);

  function resetForm(): void {
    setRetailer("");
    setOrderDate(new Date().toISOString().slice(0, 10));
    setSourceType("manual");
    setShippingAmount("0.00");
    setTaxAmount("0.00");
    setItems([emptyItem()]);
    setError(null);
    setFormErrors(emptyFormErrors());
    setSuccess(null);
  }

  function updateItem(index: number, field: keyof OrderItemDraft, value: string): void {
    setItems((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              [field]: value,
            }
          : item,
      ),
    );
  }

  function clearItemError(index: number, field: keyof ItemFieldErrors): void {
    setFormErrors((current) => ({
      ...current,
      items: {
        ...current.items,
        [index]: {
          ...current.items[index],
          [field]: undefined,
        },
      },
    }));
  }

  function addItem(): void {
    setItems((current) => [...current, emptyItem()]);
  }

  function removeItem(index: number): void {
    setItems((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  function validate(): FormErrors {
    const nextErrors = emptyFormErrors();

    if (!retailer.trim()) {
      nextErrors.retailer = "Retailer is required.";
    }

    if (!orderDate) {
      nextErrors.orderDate = "Order date is required.";
    }

    if (Number(shippingAmount) < 0) {
      nextErrors.shippingAmount = "Shipping amount must be 0 or greater.";
    }

    if (Number(taxAmount) < 0) {
      nextErrors.taxAmount = "Tax amount must be 0 or greater.";
    }

    if (!items.length) {
      nextErrors.items[0] = {
        title: "At least one order item is required.",
      };
    }

    for (const [index, item] of items.entries()) {
      const itemErrors: ItemFieldErrors = {};

      if (!item.publisher.trim()) {
        itemErrors.publisher = "Publisher is required.";
      }

      if (!item.title.trim()) {
        itemErrors.title = "Title is required.";
      }

      if (!item.issueNumber.trim()) {
        itemErrors.issueNumber = "Issue number is required.";
      }

      if (Number(item.quantity) < 1) {
        itemErrors.quantity = "Quantity must be at least 1.";
      }

      if (Number(item.rawItemPrice) < 0) {
        itemErrors.rawItemPrice = "Raw item price must be 0 or greater.";
      }

      if (Object.keys(itemErrors).length) {
        nextErrors.items[index] = itemErrors;
      }
    }

    return nextErrors;
  }

  function hasValidationErrors(nextErrors: FormErrors): boolean {
    return Boolean(
      nextErrors.retailer ||
        nextErrors.orderDate ||
        nextErrors.shippingAmount ||
        nextErrors.taxAmount ||
        Object.values(nextErrors.items).some((itemErrors) =>
          Object.values(itemErrors).some(Boolean),
        ),
    );
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    setError(null);
    setFormErrors(emptyFormErrors());

    const validationErrors = validate();
    if (hasValidationErrors(validationErrors)) {
      setFormErrors(validationErrors);
      setError("Fix the required fields below before creating the order.");
      return;
    }

    const payload: OrderCreatePayload = {
      retailer: retailer.trim(),
      order_date: orderDate,
      source_type: sourceType.trim() || "manual",
      shipping_amount: Number(shippingAmount),
      tax_amount: Number(taxAmount),
      items: items.map<OrderItemPayload>((item) => ({
        publisher: item.publisher.trim(),
        title: item.title.trim(),
        issue_number: item.issueNumber.trim(),
        cover_name: normalizeOptional(item.coverName),
        printing: normalizeOptional(item.printing),
        ratio: normalizeOptional(item.ratio),
        variant_type: normalizeOptional(item.variantType),
        cover_artist: normalizeOptional(item.coverArtist),
        quantity: Number(item.quantity),
        raw_item_price: Number(item.rawItemPrice),
      })),
    };

    setIsSubmitting(true);
    try {
      const response = await apiClient.createOrder(payload);
      setSuccess({
        orderId: response.order_id,
        totalCopiesCreated: response.total_copies_created,
        allInTotal: response.all_in_total,
      });
    } catch (submissionError) {
      if (submissionError instanceof ApiError) {
        setError(submissionError.message);
      } else {
        setError("Unable to create order right now.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (success) {
    return (
      <AppShell>
        <div className="mx-auto max-w-4xl">
          <section className="rounded-3xl border border-emerald-400/20 bg-gradient-to-br from-slate-900 via-slate-950 to-emerald-950/40 p-6 shadow-2xl shadow-emerald-950/20">
            <span className="inline-flex rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-emerald-200">
              Order Created
            </span>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Purchase logged successfully
            </h1>
            <p className="mt-3 text-sm leading-6 text-slate-300 sm:text-base">
              Order #{success.orderId} created {success.totalCopiesCreated} inventory copies with
              an all-in total of {formatCurrency(Number(success.allInTotal))}.
            </p>

            <div className="mt-6 grid gap-4 sm:grid-cols-3">
              <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                <p className="text-sm font-medium text-slate-400">Order ID</p>
                <p className="mt-2 text-2xl font-semibold text-white">#{success.orderId}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                <p className="text-sm font-medium text-slate-400">Copies Created</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {success.totalCopiesCreated}
                </p>
              </div>
              <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
                <p className="text-sm font-medium text-cyan-100">All-In Total</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {formatCurrency(Number(success.allInTotal))}
                </p>
              </div>
            </div>

            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <Link
                to={`/orders/${success.orderId}`}
                className="rounded-2xl bg-cyan-400 px-5 py-3 text-center text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
              >
                View Order
              </Link>
              <button
                type="button"
                onClick={resetForm}
                className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
              >
                Add Another Order
              </button>
              <Link
                to="/dashboard"
                className="rounded-2xl border border-white/10 px-5 py-3 text-center text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
              >
                Back to Dashboard
              </Link>
            </div>
          </section>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Manual Order Entry"
        title="Add Purchase Order"
        description="Enter a manual purchase order and create inventory copies directly in your portfolio. Each item quantity becomes the same number of physical inventory copies."
        actions={
          <Link
            to="/orders/import"
            className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
          >
            Import Order
          </Link>
        }
      />

      <div className="mx-auto max-w-7xl">
        <form className="mt-6 space-y-6" onSubmit={handleSubmit}>
          <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-300">Retailer</span>
                <input
                  value={retailer}
                  onChange={(event) => {
                    setRetailer(event.target.value);
                    setFormErrors((current) => ({ ...current, retailer: undefined }));
                  }}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  placeholder="Whatnot"
                  required
                />
                {formErrors.retailer ? (
                  <p className="text-sm text-rose-300">{formErrors.retailer}</p>
                ) : null}
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-300">Order Date</span>
                <input
                  type="date"
                  value={orderDate}
                  onChange={(event) => {
                    setOrderDate(event.target.value);
                    setFormErrors((current) => ({ ...current, orderDate: undefined }));
                  }}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  required
                />
                {formErrors.orderDate ? (
                  <p className="text-sm text-rose-300">{formErrors.orderDate}</p>
                ) : null}
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-300">Source Type</span>
                <input
                  value={sourceType}
                  onChange={(event) => setSourceType(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                />
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-300">Shipping Amount</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={shippingAmount}
                  onChange={(event) => {
                    setShippingAmount(event.target.value);
                    setFormErrors((current) => ({ ...current, shippingAmount: undefined }));
                  }}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                />
                {formErrors.shippingAmount ? (
                  <p className="text-sm text-rose-300">{formErrors.shippingAmount}</p>
                ) : null}
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-300">Tax Amount</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={taxAmount}
                  onChange={(event) => {
                    setTaxAmount(event.target.value);
                    setFormErrors((current) => ({ ...current, taxAmount: undefined }));
                  }}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                />
                {formErrors.taxAmount ? (
                  <p className="text-sm text-rose-300">{formErrors.taxAmount}</p>
                ) : null}
              </label>
            </div>

            <div className="mt-4 rounded-2xl border border-cyan-400/20 bg-cyan-400/10 px-4 py-3 text-sm text-cyan-100">
              ComicOS creates one physical `InventoryCopy` per quantity entered. A quantity of `3`
              creates exactly `3` inventory copies.
            </div>
          </section>

          <section className="space-y-4">
            {items.map((item, index) => (
              <article
                key={`order-item-${index}`}
                className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20"
              >
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm uppercase tracking-[0.18em] text-slate-500">
                      Order Item {index + 1}
                    </p>
                    <p className="mt-1 text-sm text-slate-400">
                      Enter a single purchasable comic variant line item.
                    </p>
                  </div>

                  {items.length > 1 ? (
                    <button
                      type="button"
                      disabled={isSubmitting}
                      onClick={() => removeItem(index)}
                      className="rounded-2xl border border-rose-400/20 bg-rose-400/10 px-4 py-2 text-sm font-semibold text-rose-200 transition hover:bg-rose-400/15"
                    >
                      Remove item
                    </button>
                  ) : null}
                </div>

                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <label className="space-y-2">
                    <span className="text-sm font-medium text-slate-300">Publisher</span>
                    <input
                      value={item.publisher}
                      onChange={(event) => {
                        updateItem(index, "publisher", event.target.value);
                        clearItemError(index, "publisher");
                      }}
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      placeholder="Image"
                      required
                    />
                    {formErrors.items[index]?.publisher ? (
                      <p className="text-sm text-rose-300">{formErrors.items[index]?.publisher}</p>
                    ) : null}
                  </label>

                  <label className="space-y-2">
                    <span className="text-sm font-medium text-slate-300">Title</span>
                    <input
                      value={item.title}
                      onChange={(event) => {
                        updateItem(index, "title", event.target.value);
                        clearItemError(index, "title");
                      }}
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      placeholder="Invincible"
                      required
                    />
                    {formErrors.items[index]?.title ? (
                      <p className="text-sm text-rose-300">{formErrors.items[index]?.title}</p>
                    ) : null}
                  </label>

                  <label className="space-y-2">
                    <span className="text-sm font-medium text-slate-300">Issue Number</span>
                    <input
                      value={item.issueNumber}
                      onChange={(event) => {
                        updateItem(index, "issueNumber", event.target.value);
                        clearItemError(index, "issueNumber");
                      }}
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      placeholder="1"
                      required
                    />
                    {formErrors.items[index]?.issueNumber ? (
                      <p className="text-sm text-rose-300">
                        {formErrors.items[index]?.issueNumber}
                      </p>
                    ) : null}
                  </label>

                  <label className="space-y-2">
                    <span className="text-sm font-medium text-slate-300">Cover Name</span>
                    <input
                      value={item.coverName}
                      onChange={(event) => updateItem(index, "coverName", event.target.value)}
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      placeholder="Foil Reprint Cover A"
                    />
                  </label>

                  <label className="space-y-2">
                    <span className="text-sm font-medium text-slate-300">Printing</span>
                    <input
                      value={item.printing}
                      onChange={(event) => updateItem(index, "printing", event.target.value)}
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      placeholder="Foil Edition"
                    />
                  </label>

                  <label className="space-y-2">
                    <span className="text-sm font-medium text-slate-300">Ratio</span>
                    <input
                      value={item.ratio}
                      onChange={(event) => updateItem(index, "ratio", event.target.value)}
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      placeholder="1:25"
                    />
                  </label>

                  <label className="space-y-2">
                    <span className="text-sm font-medium text-slate-300">Variant Type</span>
                    <input
                      value={item.variantType}
                      onChange={(event) => updateItem(index, "variantType", event.target.value)}
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      placeholder="Cover A"
                    />
                  </label>

                  <label className="space-y-2">
                    <span className="text-sm font-medium text-slate-300">Cover Artist</span>
                    <input
                      value={item.coverArtist}
                      onChange={(event) => updateItem(index, "coverArtist", event.target.value)}
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      placeholder="Cory Walker"
                    />
                  </label>

                  <label className="space-y-2">
                    <span className="text-sm font-medium text-slate-300">Quantity</span>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      value={item.quantity}
                      onChange={(event) => {
                        updateItem(index, "quantity", event.target.value);
                        clearItemError(index, "quantity");
                      }}
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      required
                    />
                    {formErrors.items[index]?.quantity ? (
                      <p className="text-sm text-rose-300">{formErrors.items[index]?.quantity}</p>
                    ) : null}
                  </label>

                  <label className="space-y-2">
                    <span className="text-sm font-medium text-slate-300">Raw Item Price</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={item.rawItemPrice}
                      onChange={(event) => {
                        updateItem(index, "rawItemPrice", event.target.value);
                        clearItemError(index, "rawItemPrice");
                      }}
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      required
                    />
                    {formErrors.items[index]?.rawItemPrice ? (
                      <p className="text-sm text-rose-300">
                        {formErrors.items[index]?.rawItemPrice}
                      </p>
                    ) : null}
                  </label>
                </div>
              </article>
            ))}

            <button
              type="button"
              disabled={isSubmitting}
              onClick={addItem}
              className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
            >
              Add item
            </button>
          </section>

          <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                <p className="text-sm font-medium text-slate-400">Running Subtotal</p>
                <p className="mt-3 text-2xl font-semibold text-white">
                  {formatCurrency(subtotal)}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                <p className="text-sm font-medium text-slate-400">Shipping + Tax</p>
                <p className="mt-3 text-2xl font-semibold text-white">
                  {formatCurrency(Number(shippingAmount || 0) + Number(taxAmount || 0))}
                </p>
              </div>
              <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
                <p className="text-sm font-medium text-cyan-100">Estimated All-In Total</p>
                <p className="mt-3 text-2xl font-semibold text-white">
                  {formatCurrency(estimatedAllInTotal)}
                </p>
              </div>
            </div>

            {error ? (
              <div className="mt-4">
                <StatusBanner tone="error">{error}</StatusBanner>
              </div>
            ) : null}

            {isSubmitting ? (
              <div className="mt-4">
                <StatusBanner tone="info">
                  Creating order and inventory copies. Please wait.
                </StatusBanner>
              </div>
            ) : null}

            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <button
                type="submit"
                disabled={isSubmitting}
                className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "Creating order..." : "Create order"}
              </button>
              <Link
                to="/dashboard"
                className="rounded-2xl border border-white/10 px-5 py-3 text-center text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
              >
                Back to dashboard
              </Link>
            </div>
          </section>
        </form>
      </div>
    </AppShell>
  );
}
