export async function fetchRoute(
    start,
    end,
    criterion = "time",
    userId = null  // ← DODAJ parametr
) {
  try {
    const response = await fetch(`${API_URL}/route`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start,
        end,
        criterion,
        user_id: userId,  // ← DODAJ do requestu
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Błąd pobierania trasy:", error);
    throw error;
  }
}

export async function updateUserProfile(profileData) {
  try {
    const response = await fetch(`${API_URL}/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        age_years: profileData.age_years,
        experience_level: profileData.experience_level,
        route_preference: profileData.route_preference,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data.success;
  } catch (error) {
    console.error("Błąd aktualizacji profilu:", error);
    return false;
  }
}