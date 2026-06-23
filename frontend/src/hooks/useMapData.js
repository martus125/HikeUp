//pobieranie i trzymanie danych mapy
import { useEffect, useState } from "react";
import { fetchGraph, fetchPoints } from "../api/hikeupApi";

export function useMapData() {
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [searchPoints, setSearchPoints] = useState([]);
  const [loadingGraph, setLoadingGraph] = useState(true);

  useEffect(() => {
    async function loadMapData() {
      try {
        setLoadingGraph(true);
        const [graphData, pointsData] = await Promise.all([
          fetchGraph(),
          fetchPoints(),
        ]);

        setGraph(graphData);
        setSearchPoints(pointsData);
      } catch (error) {
        console.error("Błąd pobierania danych mapy:", error);
      } finally {
        setLoadingGraph(false);
      }
    }

    loadMapData();
  }, []);

  return { graph, searchPoints, loadingGraph };
}
