/** Shared assignee text input with datalist suggestions. */
type Props = {
  value: string
  onChange: (value: string) => void
  options: string[]
  className?: string
  listId?: string
  disabled?: boolean
}

export function AssigneeInput({
  value,
  onChange,
  options,
  className = 'mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2',
  listId = 'assignee-suggestions',
  disabled = false,
}: Props) {
  return (
    <>
      <input
        className={className}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        list={listId}
        placeholder="Выберите или введите имя"
        autoComplete="off"
      />
      <datalist id={listId}>
        {options.map((name) => (
          <option key={name} value={name} />
        ))}
      </datalist>
    </>
  )
}
