import type { ViolationsResponse } from "./types";

const API_URL = import.meta.env.VITE_API_URL;

export async function fetchViolations(): Promise<ViolationsResponse> {
    try {
        const response = await fetch(API_URL)

        if (!response.ok) {
            throw new Error(`Error: ${response.status}`)
        }
        const data: ViolationsResponse = await response.json()
        return data
    }
    catch (error) {
        console.error("Request failed:", error)
        throw error
    }
}