package com.jawaadalah.ujipabrik

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import kotlin.random.Random

/** Game Ketuk Target: lingkaran muncul acak, ketuk untuk dapat poin. 30 detik. */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(GameView(this))
    }

    class GameView(context: Context) : View(context) {
        private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        private var tx = 300f
        private var ty = 400f
        private val radius = 90f
        private var skor = 0
        private var mulai = System.currentTimeMillis()
        private var selesai = false

        private fun pindah() {
            tx = Random.nextInt(120, maxOf(121, width - 120)).toFloat()
            ty = Random.nextInt(240, maxOf(241, height - 120)).toFloat()
        }

        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            canvas.drawColor(Color.rgb(18, 18, 28))
            val sisa = 30 - (System.currentTimeMillis() - mulai) / 1000
            paint.color = Color.WHITE
            paint.textSize = 56f
            if (sisa <= 0) {
                selesai = true
                canvas.drawText("Selesai! Skor akhir: $skor", 60f, height / 2f, paint)
                paint.textSize = 40f
                canvas.drawText("Ketuk layar untuk main lagi", 60f, height / 2f + 70f, paint)
                return
            }
            canvas.drawText("Skor: $skor   Waktu: $sisa", 60f, 110f, paint)
            paint.color = Color.rgb(255, 170, 40)
            canvas.drawCircle(tx, ty, radius, paint)
            postInvalidateDelayed(100)
        }

        override fun onTouchEvent(event: MotionEvent): Boolean {
            if (event.action == MotionEvent.ACTION_DOWN) {
                if (selesai) {
                    skor = 0
                    mulai = System.currentTimeMillis()
                    selesai = false
                    pindah()
                } else {
                    val dx = event.x - tx
                    val dy = event.y - ty
                    if (dx * dx + dy * dy <= radius * radius) {
                        skor++
                        pindah()
                    }
                }
                invalidate()
            }
            return true
        }
    }
}
