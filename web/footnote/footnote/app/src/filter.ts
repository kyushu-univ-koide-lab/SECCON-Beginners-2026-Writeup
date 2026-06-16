const ALLOWED_FILTER_ROOTS = new Set(["title", "body", "author"]);
const ALLOWED_OPERATORS = new Set(["eq", "contains", "startsWith"]);
const TO_ONE_RELATIONS = new Set(["author", "profile"]);
const FIELD_SEGMENT = /^[A-Za-z][A-Za-z0-9]*$/;

export class InvalidFilterError extends Error {
  constructor(message = "invalid filter") {
    super(message);
    this.name = "InvalidFilterError";
  }
}

export function isAdvancedSearch(params: {
  field: unknown;
  op: unknown;
  value: unknown;
}) {
  return (
    params.field !== undefined ||
    params.op !== undefined ||
    params.value !== undefined
  );
}

function validateFilterField(field: string) {
  const parts = field.split(".");
  const root = parts[0];

  if (!root || !ALLOWED_FILTER_ROOTS.has(root)) {
    throw new InvalidFilterError();
  }

  for (const part of parts) {
    if (!FIELD_SEGMENT.test(part)) {
      throw new InvalidFilterError();
    }
  }
}

function buildStringCondition(op: string, value: string) {
  if (!ALLOWED_OPERATORS.has(op)) {
    throw new InvalidFilterError();
  }

  if (op === "eq") {
    return { equals: value };
  }

  return { [op]: value };
}

function buildNestedWhere(
  parts: string[],
  condition: Record<string, string>,
): Record<string, unknown> {
  const [head, ...tail] = parts;

  if (!head) {
    throw new InvalidFilterError();
  }

  if (tail.length === 0) {
    return { [head]: condition };
  }

  const nested: Record<string, unknown> = buildNestedWhere(tail, condition);

  if (TO_ONE_RELATIONS.has(head)) {
    return { [head]: { is: nested } };
  }

  return { [head]: nested };
}

export function buildAdvancedWhere(query: {
  field: unknown;
  op: unknown;
  value: unknown;
}) {
  if (
    typeof query.field !== "string" ||
    typeof query.op !== "string" ||
    typeof query.value !== "string"
  ) {
    throw new InvalidFilterError();
  }

  const field = query.field.trim();
  const op = query.op.trim();
  const value = query.value;

  if (!field || !op) {
    throw new InvalidFilterError();
  }

  validateFilterField(field);
  return buildNestedWhere(field.split("."), buildStringCondition(op, value));
}

export function buildKeywordWhere(q: unknown) {
  if (typeof q !== "string" || q.trim() === "") {
    return {};
  }

  const keyword = q.trim();

  return {
    OR: [
      { title: { contains: keyword } },
      { body: { contains: keyword } },
      {
        author: {
          is: {
            profile: {
              is: {
                displayName: { contains: keyword },
              },
            },
          },
        },
      },
      {
        author: {
          is: {
            profile: {
              is: {
                bio: { contains: keyword },
              },
            },
          },
        },
      },
    ],
  };
}
