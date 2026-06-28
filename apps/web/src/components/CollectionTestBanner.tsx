import { isTestLikeCollection, useCollections } from "../context/CollectionContext";

export function CollectionTestBanner(): JSX.Element | null {
  const { activeCollection } = useCollections();

  if (!activeCollection || !isTestLikeCollection(activeCollection.collection_type)) {
    return null;
  }

  return (
    <div
      className="border-b border-amber-400 bg-amber-300 px-4 py-2 text-center text-sm font-semibold text-amber-950 sm:px-6 lg:px-8"
      role="status"
    >
      TEST COLLECTION — Changes here do not affect your real collection.
    </div>
  );
}
