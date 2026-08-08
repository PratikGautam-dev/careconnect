import { useImmerReducer } from "use-immer";
import {
  DoctorForm,
  FeatureKey,
  TimeRange,
  WizardState,
  emptyDepartment,
  emptyDoctor,
  emptyTopic,
  initialWizardState,
} from "./types";

type Action =
  | { type: "set"; field: keyof WizardState; value: unknown }
  | { type: "toggleFeature"; key: FeatureKey }
  | { type: "addDepartment" }
  | { type: "removeDepartment"; deptIndex: number }
  | { type: "setDepartmentName"; deptIndex: number; name: string }
  | { type: "addDoctor"; deptIndex: number }
  | { type: "removeDoctor"; deptIndex: number; docIndex: number }
  | { type: "setDoctorField"; deptIndex: number; docIndex: number; field: keyof DoctorForm; value: unknown }
  | { type: "toggleDoctorDay"; deptIndex: number; docIndex: number; day: string }
  | { type: "selectAllWeekdays"; deptIndex: number; docIndex: number }
  | { type: "addShift"; deptIndex: number; docIndex: number }
  | { type: "removeShift"; deptIndex: number; docIndex: number; shiftIndex: number }
  | { type: "setShift"; deptIndex: number; docIndex: number; shiftIndex: number; range: TimeRange }
  | { type: "addBreak"; deptIndex: number; docIndex: number }
  | { type: "removeBreak"; deptIndex: number; docIndex: number; breakIndex: number }
  | { type: "setBreak"; deptIndex: number; docIndex: number; breakIndex: number; range: TimeRange }
  | { type: "addTopic" }
  | { type: "removeTopic"; topicIndex: number }
  | { type: "setTopicField"; topicIndex: number; field: "topicLabel" | "answerText"; value: string };

function reducer(draft: WizardState, action: Action) {
  switch (action.type) {
    case "set":
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (draft as any)[action.field] = action.value;
      return;
    case "toggleFeature": {
      const i = draft.enabledFeatures.indexOf(action.key);
      if (i === -1) draft.enabledFeatures.push(action.key);
      else draft.enabledFeatures.splice(i, 1);
      return;
    }
    case "addDepartment":
      draft.departments.push(emptyDepartment());
      return;
    case "removeDepartment":
      draft.departments.splice(action.deptIndex, 1);
      return;
    case "setDepartmentName":
      draft.departments[action.deptIndex].name = action.name;
      return;
    case "addDoctor":
      draft.departments[action.deptIndex].doctors.push(emptyDoctor());
      return;
    case "removeDoctor":
      draft.departments[action.deptIndex].doctors.splice(action.docIndex, 1);
      return;
    case "setDoctorField": {
      const doc = draft.departments[action.deptIndex].doctors[action.docIndex];
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (doc as any)[action.field] = action.value;
      return;
    }
    case "toggleDoctorDay": {
      const doc = draft.departments[action.deptIndex].doctors[action.docIndex];
      const i = doc.workingDays.indexOf(action.day);
      if (i === -1) doc.workingDays.push(action.day);
      else doc.workingDays.splice(i, 1);
      return;
    }
    case "selectAllWeekdays": {
      const doc = draft.departments[action.deptIndex].doctors[action.docIndex];
      ["Mon", "Tue", "Wed", "Thu", "Fri"].forEach((day) => {
        if (!doc.workingDays.includes(day)) doc.workingDays.push(day);
      });
      return;
    }
    case "addShift":
      draft.departments[action.deptIndex].doctors[action.docIndex].shifts.push({ start: "", end: "" });
      return;
    case "removeShift":
      draft.departments[action.deptIndex].doctors[action.docIndex].shifts.splice(action.shiftIndex, 1);
      return;
    case "setShift":
      draft.departments[action.deptIndex].doctors[action.docIndex].shifts[action.shiftIndex] = action.range;
      return;
    case "addBreak":
      draft.departments[action.deptIndex].doctors[action.docIndex].breaks.push({ start: "", end: "" });
      return;
    case "removeBreak":
      draft.departments[action.deptIndex].doctors[action.docIndex].breaks.splice(action.breakIndex, 1);
      return;
    case "setBreak":
      draft.departments[action.deptIndex].doctors[action.docIndex].breaks[action.breakIndex] = action.range;
      return;
    case "addTopic":
      draft.topics.push(emptyTopic());
      return;
    case "removeTopic":
      draft.topics.splice(action.topicIndex, 1);
      return;
    case "setTopicField":
      draft.topics[action.topicIndex][action.field] = action.value;
      return;
  }
}

export function useWizardState() {
  return useImmerReducer(reducer, undefined, initialWizardState);
}

export type WizardDispatch = ReturnType<typeof useWizardState>[1];
