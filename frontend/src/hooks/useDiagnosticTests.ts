import { useCallback, useEffect, useState } from "react";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type Variant = {
  id: number; label: string; price: number | null; preparation_instructions: string | null; is_active: boolean;
};
export type Test = {
  id: number; category: "diagnostic" | "lab"; name: string; resource_id: string | null; is_active: boolean;
  variants: Variant[];
};
export type Resource = { id: string; name: string };

/** Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5):
 * loads + owns every mutation on the test catalog -- category switch, test
 * add/edit/delete/active-toggle, and each test's variant
 * add/edit/delete/active-toggle -- plus the resource list the test form's
 * picker needs. */
export function useDiagnosticTests() {
  const [category, setCategory] = useState<"diagnostic" | "lab">("diagnostic");
  const [tests, setTests] = useState<Test[] | null>(null);
  const [resources, setResources] = useState<Resource[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [showAddTest, setShowAddTest] = useState(false);
  const [newTestName, setNewTestName] = useState("");
  const [newTestResource, setNewTestResource] = useState("");
  const [savingTest, setSavingTest] = useState(false);

  const [editingTestId, setEditingTestId] = useState<number | null>(null);
  const [editTestName, setEditTestName] = useState("");
  const [editTestResource, setEditTestResource] = useState("");

  const [addingVariantFor, setAddingVariantFor] = useState<number | null>(null);
  const [newVariantLabel, setNewVariantLabel] = useState("");
  const [newVariantPrice, setNewVariantPrice] = useState("");
  const [newVariantPrep, setNewVariantPrep] = useState("");

  const [editingVariantId, setEditingVariantId] = useState<number | null>(null);
  const [editVariantLabel, setEditVariantLabel] = useState("");
  const [editVariantPrice, setEditVariantPrice] = useState("");
  const [editVariantPrep, setEditVariantPrep] = useState("");

  const [pendingKey, setPendingKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [testsResult, resourcesResult] = await Promise.all([
      portalFetch(`/api/portal/diagnostic-tests?category=${category}`),
      portalFetch("/api/portal/diagnostic-resources"),
    ]);
    if (testsResult.ok) setTests((testsResult.data as { tests: Test[] }).tests);
    else setTests(null);
    if (resourcesResult.ok) setResources((resourcesResult.data as { resources: Resource[] }).resources);
  }, [category]);

  useEffect(() => {
    load();
  }, [load]);

  function resourceName(id: string | null) {
    if (!id) return "None (any available doctor)";
    return resources.find((r) => r.id === id)?.name || id;
  }

  async function handleAddTest() {
    if (!newTestName.trim()) return;
    setSavingTest(true);
    setError(null);
    const result = await portalFetch("/api/portal/diagnostic-tests", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, name: newTestName.trim(), resource_id: newTestResource || null }),
    });
    setSavingTest(false);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't add test", result.error);
      return;
    }
    toast.success("Test added");
    setNewTestName(""); setNewTestResource(""); setShowAddTest(false);
    load();
  }

  function startEditTest(test: Test) {
    setEditingTestId(test.id);
    setEditTestName(test.name);
    setEditTestResource(test.resource_id || "");
  }

  async function saveEditTest(testId: number) {
    if (!editTestName.trim()) return;
    setPendingKey(`test-${testId}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/${testId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: editTestName.trim(), resource_id: editTestResource || null }),
    });
    setPendingKey(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't save test", result.error);
      return;
    }
    toast.success("Test updated");
    setEditingTestId(null);
    load();
  }

  async function toggleTestActive(test: Test) {
    setPendingKey(`test-${test.id}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/${test.id}/active`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: !test.is_active }),
    });
    setPendingKey(null);
    if (result.ok) {
      toast.success(test.is_active ? "Test deactivated" : "Test activated");
      load();
    } else if (!result.unauthorized) {
      toast.error("Couldn't update test", result.error);
    }
  }

  async function deleteTest(test: Test) {
    if (!window.confirm(`Delete "${test.name}" and all its options? Past bookings keep their stored details either way.`)) return;
    setPendingKey(`test-${test.id}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/${test.id}`, { method: "DELETE" });
    setPendingKey(null);
    if (result.ok) {
      toast.success("Test deleted");
      load();
    } else {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't delete test", result.error);
    }
  }

  async function handleAddVariant(testId: number) {
    if (!newVariantLabel.trim()) return;
    setPendingKey(`variant-new-${testId}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/${testId}/variants`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        label: newVariantLabel.trim(),
        price: newVariantPrice ? Number(newVariantPrice) : null,
        preparation_instructions: newVariantPrep.trim() || null,
      }),
    });
    setPendingKey(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't add option", result.error);
      return;
    }
    toast.success("Option added");
    setNewVariantLabel(""); setNewVariantPrice(""); setNewVariantPrep(""); setAddingVariantFor(null);
    load();
  }

  function startEditVariant(v: Variant) {
    setEditingVariantId(v.id);
    setEditVariantLabel(v.label);
    setEditVariantPrice(v.price != null ? String(v.price) : "");
    setEditVariantPrep(v.preparation_instructions || "");
  }

  async function saveEditVariant(variantId: number) {
    if (!editVariantLabel.trim()) return;
    setPendingKey(`variant-${variantId}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/variants/${variantId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        label: editVariantLabel.trim(),
        price: editVariantPrice ? Number(editVariantPrice) : null,
        preparation_instructions: editVariantPrep.trim() || null,
      }),
    });
    setPendingKey(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't save option", result.error);
      return;
    }
    toast.success("Option updated");
    setEditingVariantId(null);
    load();
  }

  async function toggleVariantActive(v: Variant) {
    setPendingKey(`variant-${v.id}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/variants/${v.id}/active`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: !v.is_active }),
    });
    setPendingKey(null);
    if (result.ok) {
      toast.success(v.is_active ? "Option deactivated" : "Option activated");
      load();
    } else if (!result.unauthorized) {
      toast.error("Couldn't update option", result.error);
    }
  }

  async function deleteVariant(v: Variant) {
    if (!window.confirm(`Delete option "${v.label}"?`)) return;
    setPendingKey(`variant-${v.id}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/variants/${v.id}`, { method: "DELETE" });
    setPendingKey(null);
    if (result.ok) {
      toast.success("Option deleted");
      load();
    } else if (!result.unauthorized) {
      toast.error("Couldn't delete option", result.error);
    }
  }

  return {
    category, setCategory, tests, resources, error, expandedId, setExpandedId,
    showAddTest, setShowAddTest, newTestName, setNewTestName, newTestResource, setNewTestResource, savingTest,
    editingTestId, setEditingTestId, editTestName, setEditTestName, editTestResource, setEditTestResource,
    addingVariantFor, setAddingVariantFor, newVariantLabel, setNewVariantLabel, newVariantPrice, setNewVariantPrice,
    newVariantPrep, setNewVariantPrep,
    editingVariantId, setEditingVariantId, editVariantLabel, setEditVariantLabel, editVariantPrice, setEditVariantPrice,
    editVariantPrep, setEditVariantPrep,
    pendingKey,
    resourceName, handleAddTest, startEditTest, saveEditTest, toggleTestActive, deleteTest,
    handleAddVariant, startEditVariant, saveEditVariant, toggleVariantActive, deleteVariant,
  };
}
