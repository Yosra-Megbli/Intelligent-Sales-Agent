import { Router, type IRouter } from "express";
import healthRouter from "./health";
import sophieRouter from "./sophie";

const router: IRouter = Router();

router.use(healthRouter);
router.use(sophieRouter);

export default router;
