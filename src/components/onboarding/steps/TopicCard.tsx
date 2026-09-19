import { Trash2 } from "lucide-react";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { TopicForm } from "../types";
import type { WizardDispatch } from "../useWizardState";

type Props = { topicIndex: number; topic: TopicForm; dispatch: WizardDispatch };

export function TopicCard({ topicIndex, topic, dispatch }: Props) {
  return (
    <div className="mb-space-3 rounded-lg border border-line bg-card p-space-4 shadow-[var(--shadow-sm)]">
      <div className="mb-space-3 flex items-center gap-space-3">
        <Input
          placeholder="Topic (e.g. Hours)"
          value={topic.topicLabel}
          onChange={(e) => dispatch({ type: "setTopicField", topicIndex, field: "topicLabel", value: e.target.value })}
          className="max-w-sm font-semibold"
        />
        <button
          type="button"
          onClick={() => dispatch({ type: "removeTopic", topicIndex })}
          className="ml-auto flex shrink-0 items-center gap-1 text-[12.5px] font-semibold text-error hover:underline"
        >
          <Trash2 size={13} /> Remove topic
        </button>
      </div>
      <Field label="Answer" className="mb-0">
        <Textarea
          rows={2}
          placeholder="e.g. We're open Mon-Sat, 9:00 AM - 6:00 PM."
          value={topic.answerText}
          onChange={(e) => dispatch({ type: "setTopicField", topicIndex, field: "answerText", value: e.target.value })}
        />
      </Field>
    </div>
  );
}
