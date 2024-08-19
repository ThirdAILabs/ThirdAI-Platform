import { createContext } from "react";
import { ModelService } from "./modelServices";

export const ModelServiceContext = createContext<ModelService | null>(null);
