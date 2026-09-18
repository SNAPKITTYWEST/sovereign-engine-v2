! qwen3asr_kernels.f90 — NARM Fortran 97 subroutine bodies
! Generated against the qwen3asr dialect symbols produced by dag_ir.py.
! Target intermediate language only — final execution is multi-arch CUFF assembly.
!
! Symbols:
!   CONV2D_GELU_F, LINEAR_F, RESIDUAL_ADD_F, LAYERNORM_F, GELU_F,
!   FLATTEN_TIME_FREQ_F, SINUSOID_POS_F, ENCODER_LAYER_F, ATTENTION_F
!
! Compile: gfortran -O2 -std=f95 -fPIC -c qwen3asr_kernels.f90

      MODULE QWEN3ASR_KERNELS
      IMPLICIT NONE
      CONTAINS

! ======================================================================
! CONV2D_GELU_F — 2-D convolution followed by GELU activation.
! IN     : [B, C_IN, H, W]  (row-major, 1-indexed)
! OUT    : [B, C_OUT, OH, OW]
! STRIDE : stride applied in each spatial dimension
! GELU(x) = 0.5·x·(1 + tanh(√(2/π)·(x + 0.044715·x³)))
! ======================================================================
      SUBROUTINE CONV2D_GELU_F(IN, OUT, B, C_IN, H, W,
     +                          C_OUT, KSIZE, STRIDE, PAD)
      IMPLICIT NONE
      INTEGER, INTENT(IN)  :: B, C_IN, H, W, C_OUT, KSIZE, STRIDE, PAD
      REAL,    INTENT(IN)  :: IN(*)
      REAL,    INTENT(OUT) :: OUT(*)

      INTEGER :: OH, OW, N, IC, OC, KH, KW, IH_P, IW_P
      INTEGER :: IDX_IN, IDX_OUT
      REAL    :: SUM_VAL, X, GELU_VAL

      OH = (H + 2*PAD - KSIZE) / STRIDE + 1
      OW = (W + 2*PAD - KSIZE) / STRIDE + 1

      DO N = 0, B-1
        DO OC = 0, C_OUT-1
          DO IH_P = 0, OH-1
            DO IW_P = 0, OW-1
              SUM_VAL = 0.0
              DO IC = 0, C_IN-1
                DO KH = 0, KSIZE-1
                  DO KW = 0, KSIZE-1
                    ! Source pixel coordinates
                    ASSOCIATE(SH => IH_P*STRIDE + KH - PAD,
     +                        SW => IW_P*STRIDE + KW - PAD)
                      IF (SH .GE. 0 .AND. SH .LT. H .AND.
     +                    SW .GE. 0 .AND. SW .LT. W) THEN
                        IDX_IN = (((N*C_IN + IC)*H + SH)*W + SW) + 1
                        SUM_VAL = SUM_VAL + IN(IDX_IN)
                      END IF
                    END ASSOCIATE
                  END DO
                END DO
              END DO
              ! GELU activation
              X = SUM_VAL
              GELU_VAL = 0.5 * X *
     +          (1.0 + TANH(0.79788456 * (X + 0.044715 * X*X*X)))
              IDX_OUT = (((N*C_OUT + OC)*OH + IH_P)*OW + IW_P) + 1
              OUT(IDX_OUT) = GELU_VAL
            END DO
          END DO
        END DO
      END DO
      END SUBROUTINE CONV2D_GELU_F

! ======================================================================
! LINEAR_F — General dense matrix multiply + bias.
! OUT[i,j] = sum_l IN[i,l]*WEIGHT[l,j] + BIAS[j]
! M×K  @ K×N  → M×N
! ======================================================================
      SUBROUTINE LINEAR_F(IN, WEIGHT, BIAS, OUT, M, K, N)
      IMPLICIT NONE
      INTEGER, INTENT(IN) :: M, K, N
      REAL, INTENT(IN)    :: IN(M,K), WEIGHT(K,N), BIAS(N)
      REAL, INTENT(OUT)   :: OUT(M,N)
      INTEGER :: I, J, L
      DO I = 1, M
        DO J = 1, N
          OUT(I,J) = BIAS(J)
          DO L = 1, K
            OUT(I,J) = OUT(I,J) + IN(I,L) * WEIGHT(L,J)
          END DO
        END DO
      END DO
      END SUBROUTINE LINEAR_F

! ======================================================================
! RESIDUAL_ADD_F — Element-wise residual connection.
! ======================================================================
      SUBROUTINE RESIDUAL_ADD_F(A, B_IN, OUT, N)
      IMPLICIT NONE
      INTEGER, INTENT(IN) :: N
      REAL, INTENT(IN)    :: A(N), B_IN(N)
      REAL, INTENT(OUT)   :: OUT(N)
      INTEGER :: I
      DO I = 1, N
        OUT(I) = A(I) + B_IN(I)
      END DO
      END SUBROUTINE RESIDUAL_ADD_F

! ======================================================================
! LAYERNORM_F — Layer normalization (standard, with mean subtraction).
! Normalizes over last dimension of size N.
! ======================================================================
      SUBROUTINE LAYERNORM_F(IN, OUT, GAMMA, BETA, N, EPS)
      IMPLICIT NONE
      INTEGER, INTENT(IN) :: N
      REAL,    INTENT(IN) :: IN(N), GAMMA(N), BETA(N), EPS
      REAL,    INTENT(OUT):: OUT(N)
      REAL :: MEAN, VAR, INV_STD, SUM_VAL
      INTEGER :: I
      SUM_VAL = 0.0
      DO I = 1, N
        SUM_VAL = SUM_VAL + IN(I)
      END DO
      MEAN = SUM_VAL / REAL(N)
      SUM_VAL = 0.0
      DO I = 1, N
        SUM_VAL = SUM_VAL + (IN(I) - MEAN)**2
      END DO
      VAR = SUM_VAL / REAL(N)
      INV_STD = 1.0 / SQRT(VAR + EPS)
      DO I = 1, N
        OUT(I) = GAMMA(I) * (IN(I) - MEAN) * INV_STD + BETA(I)
      END DO
      END SUBROUTINE LAYERNORM_F

! ======================================================================
! GELU_F — GELU activation (tanh approximation).
! ======================================================================
      SUBROUTINE GELU_F(IN, OUT, N)
      IMPLICIT NONE
      INTEGER, INTENT(IN) :: N
      REAL, INTENT(IN)    :: IN(N)
      REAL, INTENT(OUT)   :: OUT(N)
      INTEGER :: I
      REAL    :: X
      DO I = 1, N
        X = IN(I)
        OUT(I) = 0.5 * X * (1.0 + TANH(0.79788456 * (X + 0.044715*X*X*X)))
      END DO
      END SUBROUTINE GELU_F

! ======================================================================
! FLATTEN_TIME_FREQ_F — Reshape [B,C,T,F] → [B, T*C*F].
! ======================================================================
      SUBROUTINE FLATTEN_TIME_FREQ_F(IN, OUT, B, T, C, F)
      IMPLICIT NONE
      INTEGER, INTENT(IN) :: B, T, C, F
      REAL, INTENT(IN)    :: IN(B, C, T, F)
      REAL, INTENT(OUT)   :: OUT(B, T*C*F)
      INTEGER :: N, I, J, K, IDX
      DO N = 1, B
        IDX = 1
        DO I = 1, T
          DO J = 1, C
            DO K = 1, F
              OUT(N, IDX) = IN(N, J, I, K)
              IDX = IDX + 1
            END DO
          END DO
        END DO
      END DO
      END SUBROUTINE FLATTEN_TIME_FREQ_F

! ======================================================================
! SINUSOID_POS_F — Sinusoidal positional encoding.
! PE[t, 2i]   = sin(t / 10000^{2i/D})
! PE[t, 2i+1] = cos(t / 10000^{2i/D})
! ======================================================================
      SUBROUTINE SINUSOID_POS_F(OUT, SEQ_LEN, DIM)
      IMPLICIT NONE
      INTEGER, INTENT(IN) :: SEQ_LEN, DIM
      REAL, INTENT(OUT)   :: OUT(SEQ_LEN, DIM)
      INTEGER :: POS, I
      REAL    :: DIV_TERM
      DO POS = 1, SEQ_LEN
        DO I = 1, DIM, 2
          DIV_TERM = EXP(REAL(I-1) * (-LOG(10000.0) / REAL(DIM)))
          OUT(POS, I)   = SIN(REAL(POS-1) * DIV_TERM)
          IF (I+1 .LE. DIM) THEN
            OUT(POS, I+1) = COS(REAL(POS-1) * DIV_TERM)
          END IF
        END DO
      END DO
      END SUBROUTINE SINUSOID_POS_F

! ======================================================================
! ENCODER_LAYER_F — One Transformer encoder layer.
! Sequence: LN → Attn → residual → LN → FFN → residual.
! Full production path: GEMM calls lower to CUFF assembly.
! ======================================================================
      SUBROUTINE ENCODER_LAYER_F(IN, OUT, CU_SEQLENS,
     +                            D_MODEL, N_HEADS, D_FF, SEQ)
      IMPLICIT NONE
      INTEGER, INTENT(IN) :: D_MODEL, N_HEADS, D_FF, SEQ
      REAL, INTENT(IN)    :: IN(SEQ, D_MODEL), CU_SEQLENS(*)
      REAL, INTENT(OUT)   :: OUT(SEQ, D_MODEL)

      REAL :: TMP1(SEQ*D_MODEL), TMP2(SEQ*D_MODEL), TMP3(SEQ*D_MODEL)
      REAL :: GAMMA(D_MODEL), BETA(D_MODEL)
      INTEGER :: I

      ! Initialize gamma=1, beta=0 (placeholder weights)
      DO I = 1, D_MODEL
        GAMMA(I) = 1.0
        BETA(I)  = 0.0
      END DO

      ! Flatten IN to 1-D for subroutine calls
      CALL LAYERNORM_F(IN, TMP1, GAMMA, BETA, SEQ*D_MODEL, 1.0E-6)

      ! Simplified attention: single linear projection (full attn in CUFF path)
      CALL LINEAR_F(TMP1, GAMMA, BETA, TMP2, SEQ, D_MODEL, D_MODEL)

      ! Residual after attention
      CALL RESIDUAL_ADD_F(IN, TMP2, TMP3, SEQ*D_MODEL)

      ! LayerNorm → FFN1 → GELU → FFN2
      CALL LAYERNORM_F(TMP3, TMP1, GAMMA, BETA, SEQ*D_MODEL, 1.0E-6)
      CALL LINEAR_F(TMP1, GAMMA, BETA, TMP2, SEQ, D_MODEL, D_FF)
      CALL GELU_F(TMP2, TMP1, SEQ*D_FF)
      CALL LINEAR_F(TMP1, GAMMA, BETA, TMP2, SEQ, D_FF, D_MODEL)

      ! Residual after FFN
      CALL RESIDUAL_ADD_F(TMP3, TMP2, OUT, SEQ*D_MODEL)
      END SUBROUTINE ENCODER_LAYER_F

! ======================================================================
! ATTENTION_F — Placeholder; production path replaces with RECON_ATTENTION.
! In NARM the softmax here is eliminated; reconstruction kernel used instead.
! ======================================================================
      SUBROUTINE ATTENTION_F(Q, K_IN, V, OUT, SEQ, HEAD_DIM, N_HEADS)
      IMPLICIT NONE
      INTEGER, INTENT(IN) :: SEQ, HEAD_DIM, N_HEADS
      REAL, INTENT(IN)    :: Q(*), K_IN(*), V(*)
      REAL, INTENT(OUT)   :: OUT(*)
      ! Production: replaced by raw_recon_attention (no softmax)
      END SUBROUTINE ATTENTION_F

      END MODULE QWEN3ASR_KERNELS
