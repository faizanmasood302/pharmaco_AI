from enum import StrEnum


class ErrorCode(StrEnum):
    PATIENT_NOT_FOUND = "PATIENT_NOT_FOUND"
    MEDICATION_NOT_FOUND = "MEDICATION_NOT_FOUND"
    INVALID_PHENOTYPE = "INVALID_PHENOTYPE"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    AUTH_FAILED = "AUTH_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class PharmacogenomicError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        retriable: bool = False,
        details: dict | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retriable = retriable
        self.details = details or {}
        super().__init__(message)


class PatientNotFoundError(PharmacogenomicError):
    def __init__(self, patient_id: str):
        super().__init__(
            code=ErrorCode.PATIENT_NOT_FOUND,
            message=f"Patient {patient_id} not found in database or seed data.",
            status_code=404,
            details={"patient_id": patient_id},
        )


class MedicationNotFoundError(PharmacogenomicError):
    def __init__(self, medication: str):
        super().__init__(
            code=ErrorCode.MEDICATION_NOT_FOUND,
            message=f"Medication '{medication}' is not present in the current clinical knowledge base formulary.",
            status_code=400,
            details={"medication": medication},
        )


class InvalidPhenotypeError(PharmacogenomicError):
    def __init__(self, patient_id: str, gene: str):
        super().__init__(
            code=ErrorCode.INVALID_PHENOTYPE,
            message=f"Missing or invalid phenotype data for gene {gene}.",
            status_code=422,
            details={"patient_id": patient_id, "gene": gene},
        )


class AuthFailedError(PharmacogenomicError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(code=ErrorCode.AUTH_FAILED, message=message, status_code=401)


class EvaluationFailedError(PharmacogenomicError):
    def __init__(self, message: str = "Evaluation pipeline failed"):
        super().__init__(
            code=ErrorCode.EVALUATION_FAILED,
            message=message,
            status_code=500,
            retriable=True,
        )


class InternalServerError(PharmacogenomicError):
    def __init__(self, message: str = "An unexpected internal server error occurred"):
        super().__init__(
            code=ErrorCode.INTERNAL_ERROR, message=message, status_code=500
        )
