//wyszukiwanie punktów po pierwszych literach
import { getPointName } from "../utils/points";

export function SearchInput({
  label,
  value,
  suggestions,
  isActive,
  onFocus,
  onBlur,
  onChange,
  onSelect,
}) {
  return (
    <div className="search-field">
      <label>{label}</label>
      <input
        type="text"
        value={value}
        placeholder="Wpisz nazwę punktu"
        onFocus={onFocus}
        onBlur={onBlur}
        onChange={(event) => onChange(event.target.value)}
      />

      {isActive && suggestions.length > 0 && (
        <div className="suggestions">
          {suggestions.map((point) => (
            <button
              key={point.id}
              type="button"
              onMouseDown={(event) => {
                event.preventDefault();
                onSelect(point);
              }}
            >
              <span>{getPointName(point)}</span>
              <small>{point.type || "punkt trasy"}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
