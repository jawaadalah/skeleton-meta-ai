package com.jawaadalah.jumjawa

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import kotlin.math.max
import kotlin.math.min

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(GameView(this))
    }
}

private class GameView(context: Context) : View(context) {

    private val bgPaint = Paint().apply { color = Color.BLACK }
    private val textPaint = Paint().apply {
        color = Color.WHITE
        textSize = 64f
        isAntiAlias = true
    }
    private val playerPaint = Paint().apply { color = Color.YELLOW }

    private var playerX = 0f
    private var playerY = 0f
    private var playerRadius = 50f
    private var velocityY = 0f
    private val gravity = 1.5f
    private val jumpVelocity = -30f

    private var score = 0
    private var isGameOver = false

    init {
        // Force view to be focusable to receive touch events
        isFocusable = true
        isFocusableInTouchMode = true
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        playerX = w / 2f
        resetPlayerPosition()
    }

    private fun resetPlayerPosition() {
        playerY = height - playerRadius - 10f
        velocityY = 0f
    }

    private fun resetGame() {
        score = 0
        isGameOver = false
        resetPlayerPosition()
    }

    override fun onDraw(canvas: Canvas) {
        // Background
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), bgPaint)

        // Player
        canvas.drawCircle(playerX, playerY, playerRadius, playerPaint)

        // Score
        canvas.drawText("Score: $score", 20f, 80f, textPaint)

        // Game Over message
        if (isGameOver) {
            val msg = "Game Over\nTap to Restart"
            val lines = msg.split("\n")
            for (i in lines.indices) {
                val y = height / 2f + i * (textPaint.textSize + 20f)
                val textWidth = textPaint.measureText(lines[i])
                val x = (width - textWidth) / 2f
                canvas.drawText(lines[i], x, y, textPaint)
            }
        } else {
            // Update physics
            velocityY += gravity
            playerY += velocityY

            // Floor collision
            if (playerY + playerRadius > height) {
                playerY = height - playerRadius
                isGameOver = true
            }

            // Increment score
            score = min(score + 1, Int.MAX_VALUE)
        }

        // Loop
        postInvalidateDelayed(16)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (event.action == MotionEvent.ACTION_DOWN) {
            if (isGameOver) {
                resetGame()
            } else {
                velocityY = jumpVelocity
            }
            return true
        }
        return super.onTouchEvent(event)
    }
}